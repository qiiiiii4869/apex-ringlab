"""Train supervised offset regressors; select only inside the frozen library split."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
import scipy
import threadpoolctl
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from threadpoolctl import threadpool_limits

from .data import DATA_FILE, ROOT, load_records, write_json_atomic
from .evaluate import MAIN_RADIUS, SEED, assert_no_leakage, error_summary, evaluate_queries
from .model import FEATURE_SCHEMA, features, predict_centers, target_offset


def candidate_configs():
    return ([{"family": "ridge", "degree": 1, "alpha": alpha} for alpha in (1, 10, 100)]
            + [{"family": "ridge", "degree": 2, "alpha": alpha} for alpha in (10, 100)]
            + [{"family": "extra_trees", "min_samples_leaf": leaf, "n_estimators": 200} for leaf in (2, 10)]
            + [{"family": "hist_gradient_boosting", "max_leaf_nodes": leaves,
                "l2_regularization": 10, "max_iter": 200} for leaves in (7, 15)])


def build_estimator(config):
    family = config["family"]
    if family == "ridge":
        return make_pipeline(PolynomialFeatures(degree=config["degree"], include_bias=False),
                             StandardScaler(), Ridge(alpha=config["alpha"]))
    if family == "extra_trees":
        return ExtraTreesRegressor(n_estimators=config["n_estimators"], min_samples_leaf=config["min_samples_leaf"],
                                   random_state=SEED, n_jobs=2)
    if family == "hist_gradient_boosting":
        return MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=config["max_iter"],
            max_leaf_nodes=config["max_leaf_nodes"], l2_regularization=config["l2_regularization"],
            early_stopping=False, random_state=SEED))
    raise ValueError(f"Unknown model family: {family}")


def checked_partitions(records, manifest, fingerprint):
    if manifest.get("dataset_sha256") != fingerprint:
        raise ValueError("正式库与冻结分区数据指纹不同，不能沿用旧分区训练")
    assert_no_leakage(manifest["groups"])
    if any(group["split"] not in ("library", "validation", "test") for group in manifest["groups"]):
        raise ValueError("分区名称无效")
    assignments = {item: g["split"] for g in manifest["groups"] for item in g["record_ids"]}
    group_ids = {item: g["group_id"] for g in manifest["groups"] for item in g["record_ids"]}
    if set(assignments) != {r["id"] for r in records}:
        raise ValueError("冻结分区必须恰好覆盖正式库全部样本")
    # Check the actual current aliases, not only the stored manifest text.
    actual = []
    for group in manifest["groups"]:
        aliases = {alias for r in records if r["id"] in group["record_ids"]
                   for alias in [r.get("source_game_id"), *r.get("source_game_ids", [])] if alias}
        if aliases != set(group["source_game_ids"]):
            raise ValueError("分区源对局别名与正式库不一致")
        actual.append({**group, "source_game_ids": sorted(aliases)})
    assert_no_leakage(actual)
    cohort = [r for r in records if r["source_mode"] == "PUBLIC" and r["game_mode"] == "ranked"
              and r["final_ring"].get("r") == MAIN_RADIUS]
    scopes = {(r["map_version"], r.get("build")) for r in cohort}
    if len(scopes) != 1:
        raise ValueError("本训练入口要求单一地图 / build 分组，不能混用多个版本")
    train = sorted([r for r in cohort if assignments[r["id"]] == "library"], key=lambda r: r["id"])
    validation = sorted([r for r in cohort if assignments[r["id"]] == "validation"], key=lambda r: r["id"])
    if not train or not validation:
        raise ValueError("训练与验证分区不能为空")
    return train, validation, group_ids, scopes.pop()


def prediction_rows(records, centers, raw=None):
    centers = np.asarray(centers, dtype=float)
    if centers.shape != (len(records), 2) or not np.isfinite(centers).all():
        raise ValueError("评分预测与样本数量不一致或圆心无效")
    rows = []
    for index, (record, center) in enumerate(zip(records, centers)):
        target = record["final_ring"]
        error = float(np.linalg.norm(center - np.array([target["x"], target["y"]])))
        rows.append({"query_id": record["id"], "prediction": {"x": float(center[0]), "y": float(center[1])},
                     "center_error": error, "target_radius": target["r"], "hit": bool(error <= target["r"]),
                     "within_200": bool(error <= 200), "within_400": bool(error <= 400),
                     "geometry_adjusted": bool(raw is not None and np.linalg.norm(center - raw[index]) > 1e-7)})
    return rows


def metrics(rows):
    return {"count": len(rows), "center_error": error_summary([r["center_error"] for r in rows]),
            "circle_coverage": sum(r["hit"] for r in rows) / len(rows),
            "within_200": sum(r["within_200"] for r in rows) / len(rows),
            "within_400": sum(r["within_400"] for r in rows) / len(rows),
            "geometry_adjustments": sum(r["geometry_adjusted"] for r in rows)}


def select_candidate(candidates):
    # Predefined primary objective, then tail error, then stable config tie-break.
    return min(candidates, key=lambda c: (c["cv"]["center_error"]["mean"], c["cv"]["center_error"]["p90"],
                                          json.dumps(c["config"], sort_keys=True)))


def train_stage(train, validation, group_ids, stages, output, model_path, fingerprint, scope):
    train = [r for r in train if len(r["known_rings"]) >= stages]
    validation = [r for r in validation if len(r["known_rings"]) >= stages]
    observed = [r["known_rings"][:stages] for r in train]
    x = np.vstack([features(o) for o in observed])
    y = np.vstack([target_offset(r, stages) for r in train])
    groups = np.array([group_ids[r["id"]] for r in train])
    splitter = GroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    folds = list(splitter.split(x, y, groups))
    fold_records = [{"fit_ids": [train[i]["id"] for i in fit], "holdout_ids": [train[i]["id"] for i in holdout]}
                    for fit, holdout in folds]
    comparisons = []
    for number, config in enumerate(candidate_configs(), 1):
        started = time.monotonic()
        out_of_fold, raw_out_of_fold = np.zeros((len(train), 2)), np.zeros((len(train), 2))
        for fit, holdout in folds:
            estimator = build_estimator(config)
            estimator.fit(x[fit], y[fit])
            predicted, raw = predict_centers(estimator, [observed[i] for i in holdout], MAIN_RADIUS)
            out_of_fold[holdout], raw_out_of_fold[holdout] = predicted, raw
        rows = prediction_rows(train, out_of_fold, raw_out_of_fold)
        comparisons.append({"config": config, "cv": metrics(rows), "out_of_fold_predictions": rows,
                            "fit_seconds": time.monotonic() - started})
        print(json.dumps({"stages": stages, "candidate": number, "config": config,
                          "cv_mean_error": comparisons[-1]["cv"]["center_error"]["mean"]}), flush=True)
    winner = select_candidate(comparisons)
    # Winner fixed before validation labels are used for scoring.
    write_json_atomic(output / f"stage-{stages}-selection.json", {"dataset_sha256": fingerprint,
        "selection_rule": "minimum grouped CV mean center error; P90 then canonical config tie-break",
        "selected": winner["config"], "cross_validation": comparisons, "folds": fold_records})
    estimator = build_estimator(winner["config"])
    estimator.fit(x, y)
    artifact = {"estimator": estimator, "config": winner["config"], "stages": stages,
                "feature_schema": FEATURE_SCHEMA, "target_radius": MAIN_RADIUS, "dataset_sha256": fingerprint,
                "scope": {"map_version": scope[0], "build": scope[1], "source_mode": "PUBLIC"},
                "train_ids": [r["id"] for r in train], "sklearn_version": sklearn.__version__}
    model_path.mkdir(parents=True, exist_ok=True)
    filename = model_path / f"stage-{stages}.joblib"
    temporary = filename.with_suffix(".joblib.tmp")
    joblib.dump(artifact, temporary, compress=3)
    temporary.replace(filename)
    observations = [r["known_rings"][:stages] for r in validation]
    predictions, raw = predict_centers(estimator, observations, MAIN_RADIUS)
    learned_rows = prediction_rows(validation, predictions, raw)
    center_rows = prediction_rows(validation, np.array([[o[-1]["x"], o[-1]["y"]] for o in observations]))
    retrieval = evaluate_queries(train, validation, stages)
    by_id = {r["id"]: r for r in train}
    retrieval_centers = np.array([[by_id[row["candidate_ids"][0]]["final_ring"][key] for key in ("x", "y")] for row in retrieval])
    nearest_rows = prediction_rows(validation, retrieval_centers)
    cv_baseline = prediction_rows(train, np.array([[o[-1]["x"], o[-1]["y"]] for o in observed]))
    return {"stages": stages, "config": winner["config"], "training_count": len(train), "validation_count": len(validation),
            "features": x.shape[1], "selected_cv": winner["cv"], "center_baseline_cv": metrics(cv_baseline),
            "model_file": str(filename.relative_to(ROOT)) if filename.is_relative_to(ROOT) else str(filename),
            "model_sha256": hashlib.sha256(filename.read_bytes()).hexdigest(),
            "validation": {"learned": {"metrics": metrics(learned_rows), "predictions": learned_rows},
                           "latest_known_center": {"metrics": metrics(center_rows), "predictions": center_rows},
                           "retrieval_top1": {"metrics": metrics(nearest_rows), "predictions": nearest_rows}},
            "folds": fold_records}


def render_report(result):
    lines = ["# 首轮机器学习训练报告", "", f"生成时间：{result['generated_at']}。数据 SHA-256：`{result['dataset_sha256']}`。", "",
             "本次实际训练监督回归模型，学习源站最终圈圆心相对于最后一个已知圈的偏移。尚未验证真实截图或当前排位实战效果。", "",
             "## 数据与选型", "",
             f"沿用冻结源对局分区。仅 PUBLIC 排位、目标半径 728：训练 {result['train_count']} 条，验证 {result['validation_count']} 条。半径 1,216 记录保留在正式库，未参与训练；ALGS 未混入。",
             f"旧 {result['reserved_test_count']} 条 PUBLIC 测试集的效果此前已查看，因此本次不评分、不调参、不加入训练。后续需要新的独立对局验收；本报告的交叉验证与验证结果不称为最终测试准确率。",
             "所有源对局别名连通组保持同分区；训练内部进行 5 折分组交叉验证。九种预设配置只按训练折外的平均圆心误差选择，P90 与配置字符串用于同分时排序。胜出配置落盘后才对验证集评分，没有按验证成绩重选或重新训练。", "",
             "输入特征仅使用已知圈：归一化地图圆心与半径、相对最后一个已知圈的圆心偏移与半径比、相邻圈移动距离。目标为 (最终圆心−最后已知圆心)/最后已知半径；各圈数分别训练模型。",
             "比较 Ridge（一阶 / 二阶、L2 正则）、ExtraTrees（200 棵随机树）、HistGradientBoosting（两个坐标分别回归）。训练损失为平方误差，选型指标为还原到地图坐标后的平均欧氏误差。",
             "Ridge 的标准化只在每个训练折拟合。随机种子固定为 20261012；CPU 线程上限 2。版本与完整配置见 manifest.json，逐折 ID、九种结果与折外预测见 stage-N-selection.json。",
             "预测还原后仅用已知圈和固定目标半径做几何约束，使目标圈位于已知安全区内（沿用正式库 20 坐标容差）及地图范围内；投影不读取真实最终圈。输出不包含校准概率，也不能确认内部最终圈阶段。", "",
             "## 训练内部交叉验证", "", "| 输入 | 胜出配置 | 特征数 | 折外平均圆心误差 | 折外中位误差 | 已知圈圆心平均误差 |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    for stage in result["stages"]:
        m = stage["selected_cv"]["center_error"]
        lines.append(f"| 前 {stage['stages']} 圈 | `{json.dumps(stage['config'], ensure_ascii=False)}` | {stage['features']} | {m['mean']:.1f} | {m['median']:.1f} | {stage['center_baseline_cv']['center_error']['mean']:.1f} |")
    lines += ["", "## 固定验证集比较", "", "三种方法各输出一个圆心，使用同一验证样本进行公平比较。坐标单位对应地图边长 16,384，换算到 1536 底图像素乘 1536/16384。",
              "圈内覆盖表示预测圆心落入真实目标圈（半径 728），不表示精确预测、胜率或概率。200 / 400 坐标阈值分别约为 18.75 / 37.5 底图像素，只是本次误差刻度，没有赋予实战距离含义。", "",
              "| 输入 | 方法 | 样本 | 平均误差 | 中位误差 | P90 | P95 | ≤200 | ≤400 | 圈内覆盖 |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    labels = {"learned": "训练模型", "latest_known_center": "最近已知圈圆心", "retrieval_top1": "历史检索第一候选"}
    for stage in result["stages"]:
        for method, item in stage["validation"].items():
            m = item["metrics"]; e = m["center_error"]
            lines.append(f"| 前 {stage['stages']} 圈 | {labels[method]} | {m['count']} | {e['mean']:.1f} | {e['median']:.1f} | {e['p90']:.1f} | {e['p95']:.1f} | {m['within_200']:.1%} | {m['within_400']:.1%} | {m['circle_coverage']:.1%} |")
    lines += ["", "## 结论与下一步", ""]
    for stage in result["stages"]:
        learned = stage["validation"]["learned"]["metrics"]
        baseline = stage["validation"]["latest_known_center"]["metrics"]
        change = (baseline["center_error"]["mean"] - learned["center_error"]["mean"]) / baseline["center_error"]["mean"]
        lines.append(f"- 前 {stage['stages']} 圈：相对最近已知圈圆心，验证平均误差变化为 {change:+.1%}（正数为降低），圈内覆盖 {learned['circle_coverage']:.1%} vs {baseline['circle_coverage']:.1%}。模型选择未使用这些验证成绩。")
    lines += ["", "结果属于首轮历史数据实验。数据量有限，地图版本和 build 未核实，第三圈圆心覆盖高还受几何包含关系影响，不能单凭覆盖率认定模型已足够实用。模型可能减少平均误差而降低宽松圈内覆盖，必须同时看较小阈值和尾部误差。",
              "下一步可以将保存的研究模型接入手动圈位网页，同时展示历史候选与简单基线，并继续用真实截图验证。最终模型效果需要新增独立对局，采集扩容仍需明确新目标。", "",
              "## 复现与推理", "", "```powershell", "& '.\\.venv\\Scripts\\python.exe' -m ringlab.train",
              "& '.\\.venv\\Scripts\\python.exe' -m ringlab.model 'data\\training\\example-query.json'",
              "& '.\\.venv\\Scripts\\python.exe' -m unittest discover -s tests -v", "```", "",
              "models/stage-1.joblib、stage-2.joblib、stage-3.joblib 保存训练模型。训练仅使用训练分区，没有把验证集回灌拟合。推理输入必须明确圈次、map_version、build 和 source_mode；不同版本 / 来源拒绝使用本模型。build=null 只表示未知，不保证当前机制相同。示例只包含已知圈与上下文，无最终圈标签。", "",
              "算法参考：[Ridge 官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)、[ExtraTrees 官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.ExtraTreesRegressor.html)、[多输出回归官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.multioutput.MultiOutputRegressor.html)。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "training")
    parser.add_argument("--models", type=Path, default=ROOT / "models")
    args = parser.parse_args()
    fingerprint = hashlib.sha256(DATA_FILE.read_bytes()).hexdigest()
    manifest_path = ROOT / "data" / "evaluation" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = load_records()
    train, validation, group_ids, scope = checked_partitions(records, manifest, fingerprint)
    reserved_ids = {item for group in manifest["groups"] if group["split"] == "test" for item in group["record_ids"]}
    reserved_ids &= {r["id"] for r in records if r["source_mode"] == "PUBLIC" and r["final_ring"].get("r") == MAIN_RADIUS}
    args.output.mkdir(parents=True, exist_ok=True)
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "dataset_sha256": fingerprint,
              "split_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "seed": SEED, "train_count": len(train), "validation_count": len(validation),
              "reserved_test_count": len(reserved_ids), "reserved_test_ids": sorted(reserved_ids),
              "scope": {"map_version": scope[0], "build": scope[1], "source_mode": "PUBLIC"},
              "feature_schema": FEATURE_SCHEMA, "target_radius": MAIN_RADIUS,
              "versions": {"python": platform.python_version(), "numpy": np.__version__,
                           "sklearn": sklearn.__version__, "joblib": joblib.__version__,
                           "scipy": scipy.__version__, "threadpoolctl": threadpoolctl.__version__},
              "selection_rule": "training-only 5-fold source-group CV mean map-coordinate center error",
              "old_test_used": False, "stages": []}
    with threadpool_limits(limits=2):
        for stages in (1, 2, 3):
            result["stages"].append(train_stage(train, validation, group_ids, stages, args.output,
                                                args.models, fingerprint, scope))
    if hashlib.sha256(DATA_FILE.read_bytes()).hexdigest() != fingerprint:
        raise ValueError("训练期间正式库发生变化，不能发布混合版本结果")
    write_json_atomic(args.output / "results.json", result)
    write_json_atomic(args.output / "manifest.json", {**{key: value for key, value in result.items() if key != "stages"},
        "training_ids": [r["id"] for r in train], "validation_ids": [r["id"] for r in validation],
        "configs": candidate_configs(), "models": [{key: stage[key] for key in ("stages", "config", "model_file", "model_sha256")}
                                                  for stage in result["stages"]]})
    write_json_atomic(args.output / "example-query.json", {"known_rings": validation[0]["known_rings"],
        "map_version": scope[0], "build": scope[1], "source_mode": "PUBLIC"})
    (args.output / "TRAINING_REPORT.md").write_text(render_report(result), encoding="utf-8")
    print(json.dumps({"completed": True, "stages": [{"stages": s["stages"], "config": s["config"],
        "validation": {key: value["metrics"] for key, value in s["validation"].items()}} for s in result["stages"]]}), flush=True)


if __name__ == "__main__":
    main()
