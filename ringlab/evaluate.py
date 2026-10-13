"""Frozen source-game holdout evaluation of the existing retrieval baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .data import COORD_SIZE, DATA_FILE, ROOT, load_records, write_json_atomic
from .retrieval import retrieve

SEED = 20261012
MAIN_RADIUS = 728


def source_ids(record):
    return sorted({value for value in [record.get("source_game_id"), *record.get("source_game_ids", [])] if value})


def source_groups(records):
    """Union every alias, including transitive overlaps and cross-mode overlaps."""
    parent = {r["id"]: r["id"] for r in records}

    def root(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    owners = {}
    for record in sorted(records, key=lambda r: r["id"]):
        for game_id in source_ids(record):
            if game_id in owners:
                a, b = root(record["id"]), root(owners[game_id])
                parent[max(a, b)] = min(a, b)
            else:
                owners[game_id] = record["id"]
    groups = defaultdict(list)
    for record in records:
        groups[root(record["id"])].append(record)
    return [sorted(group, key=lambda r: r["id"]) for _, group in sorted(groups.items())]


def make_split(records, seed=SEED):
    # Stratify whole groups, never individual rows. Unknown build remains a distinct key.
    strata = defaultdict(list)
    for group in source_groups(records):
        scope = sorted({(r["source_mode"], r["map_version"], str(r.get("build"))) for r in group})
        strata[json.dumps(scope)].append(group)
    assignments = []
    for scope, groups in sorted(strata.items()):
        rng = random.Random(f"{seed}:{scope}")
        rng.shuffle(groups)
        library_end, validation_end = int(len(groups) * .6), int(len(groups) * .8)
        for index, group in enumerate(groups):
            split = "library" if index < library_end else "validation" if index < validation_end else "test"
            aliases = sorted({alias for r in group for alias in source_ids(r)})
            assignments.append({"group_id": min(r["id"] for r in group), "split": split,
                                "record_ids": [r["id"] for r in group], "source_game_ids": aliases})
    return sorted(assignments, key=lambda g: g["group_id"])


def assert_no_leakage(assignments):
    source_owner, record_owner = {}, {}
    for group in assignments:
        for kind, values, owners in (("source", group["source_game_ids"], source_owner),
                                     ("record", group["record_ids"], record_owner)):
            for value in values:
                if value in owners:
                    raise ValueError(f"Repeated {kind} ID across groups: {value}")
                owners[value] = group["split"]


def compatible_pool(library, query, mix_modes=False):
    return [r for r in library if r["map_version"] == query["map_version"]
            and r.get("build") == query.get("build")
            and (mix_modes or r["source_mode"] == query["source_mode"])]


def center_error(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def percentile(values, quantile):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * quantile
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def error_summary(values):
    return {"mean": sum(values) / len(values) if values else None,
            "median": percentile(values, .5), "p90": percentile(values, .9), "p95": percentile(values, .95)}


def evaluate_queries(library, queries, stages, mix_modes=False):
    rows = []
    for query in sorted(queries, key=lambda r: r["id"]):
        if len(query["known_rings"]) < stages:
            continue
        observed = query["known_rings"][:stages]
        pool = [r for r in compatible_pool(library, query, mix_modes) if len(r["known_rings"]) >= stages]
        if set(source_ids(query)) & {alias for r in pool for alias in source_ids(r)}:
            raise ValueError("Query source game occurs in reference library")
        result = retrieve(pool, observed, query["map_version"], limit=5)
        candidates = result["candidates"]
        errors = [center_error(candidate["final_ring"], query["final_ring"]) for candidate in candidates]
        radius = query["final_ring"].get("r")
        hits = {str(k): bool(errors[:k]) and radius is not None and min(errors[:k]) <= radius for k in (1, 3, 5)}
        exact_input = any(r["known_rings"][:stages] == observed for r in pool)
        mean_center = {key: sum(r["final_ring"][key] for r in pool) / len(pool) for key in ("x", "y")} if pool else None
        rows.append({"query_id": query["id"], "stages": stages, "target_radius": radius,
                     "source_mode": query["source_mode"], "pool_size": len(pool), "status": result["status"],
                     "exact_input_seen": exact_input, "candidate_ids": [c["id"] for c in candidates],
                     "candidate_center_errors": errors, "hits": hits,
                     "latest_known_center_error": center_error(observed[-1], query["final_ring"]),
                     "historical_mean_center_error": center_error(mean_center, query["final_ring"]) if mean_center else None})
    return rows


def summarize(rows):
    errors = [r["candidate_center_errors"][0] for r in rows if r["candidate_center_errors"]]
    summary = {"queries": len(rows), "predictions": len(errors), "abstentions": len(rows) - len(errors),
               "top1_center_error": error_summary(errors),
               "top5_oracle_center_error": error_summary([min(r["candidate_center_errors"]) for r in rows if r["candidate_center_errors"]]),
               "coverage": {str(k): sum(r["hits"][str(k)] for r in rows) / len(rows) if rows else None for k in (1, 3, 5)},
               "latest_known_center_error": error_summary([r["latest_known_center_error"] for r in rows]),
               "latest_known_center_coverage": sum(r["latest_known_center_error"] <= r["target_radius"] for r in rows if r["target_radius"] is not None) / len(rows) if rows else None,
               "historical_mean_center_error": error_summary([r["historical_mean_center_error"] for r in rows if r["historical_mean_center_error"] is not None]),
               "status_counts": dict(Counter(r["status"] for r in rows))}
    return summary


def label_audit(records, raw_path):
    from .retrieval import audit
    result = audit(records)
    conflict_ids = {item for group in result["conflict_examples"] for item in group}
    known_radii = {str(stage): Counter(str(r["known_rings"][stage - 1]["r"]) for r in records if len(r["known_rings"]) >= stage)
                   for stage in (1, 2, 3)}
    modal_radii = {stage: histogram.most_common(1)[0][0] for stage, histogram in known_radii.items() if histogram}
    unusual_known = [r for r in records if any(str(ring["r"]) != modal_radii[str(ring["stage"])] for ring in r["known_rings"])]
    evidence_ids = conflict_ids | {r["id"] for r in unusual_known}
    game_records = defaultdict(list)
    for record in records:
        if record["id"] in evidence_ids:
            for game_id in source_ids(record):
                game_records[game_id].append(record["id"])
    evidence = []
    for line_number, line in enumerate(raw_path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        pair = json.loads(line)
        game_id = pair.get("reveal", {}).get("gameId")
        matching = game_records.get(game_id, [])
        if matching:
            evidence.append({"record_ids": matching, "line": line_number,
                             "line_utf8_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                             "batch_id": pair.get("batch_id"), "round": pair.get("round"),
                             "collected_at": pair.get("collected_at"), "source_game_id": game_id,
                             "known_rings": pair["known"]["rings"], "final_ring": pair["reveal"]["finalRing"]})
    return {"audit": result, "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            "radius_counts": dict(Counter(str(r["final_ring"].get("r")) for r in records)),
            "known_radius_counts": {stage: dict(histogram) for stage, histogram in known_radii.items()},
            "unusual_known_radius_records": unusual_known,
            "conflict_records": [r for r in records if r["id"] in conflict_ids], "raw_evidence": evidence,
            "official_page": "https://apexlegendsstatus.com/algs/ring-guessr",
            "official_page_checked_on": "2026-10-12",
            "page_evidence": "页面说明展示前三圈并猜测 last ring 的圆心，没有定义内部目标圈次。",
            "conclusion": "原始响应确认目标差异；内部圈次、build、差异原因仍未确认，不能推断服务器刷圈机制。",
            "primary_policy": "主评估限定源站目标半径 728；其他半径仅在全标签敏感性分析中使用，正式库不删改。",
            "replay_constraint": "此前回放接口出现 HTTP 429 / CAPTCHA_REQUIRED，本次未重试受限回放接口。"}


def render_report(result):
    scenarios = result["scenarios"]
    main = scenarios["public_r728"]["test"]
    lines = ["# 独立对局检索评估", "", f"生成时间：{result['generated_at']}。数据 SHA-256：`{result['dataset_sha256']}`。", "",
             "## 结论与范围", "", "本报告仅评估历史最近邻检索基线，不涉及机器学习训练。输入是源站精确圈坐标，未包含截图识别误差。",
             "PUBLIC 按用户确认视为排位；主评估使用目标半径 728 的样本。游戏时间、build 和内部目标圈次仍未知，结果只适用于本次冻结样本。", "",
             f"固定测试集包含 {main['1']['overall']['queries']} 条 PUBLIC 样本。首圈、前两圈、前三圈的前五候选覆盖率分别为 "
             + "、".join(f"{main[str(stage)]['overall']['coverage']['5']:.1%}" for stage in (1, 2, 3)) + "。首圈单点预测仍较弱；更多已知圈能明显缩小候选范围。",
             f"前三圈检索第一候选的覆盖率为 {main['3']['overall']['coverage']['1']:.1%}，直接使用第三圈圆心的覆盖率为 {main['3']['overall']['latest_known_center_coverage']:.1%}。检索中位圆心误差略小，但尾部误差更大；当前单候选排序未超过这个简单基线。前五候选与单个基线的猜测次数不同，不能用两者覆盖率差直接声称模型提升。", "",
             "## 分区与防泄漏", "",
             f"随机种子 `{result['seed']}`；按全部源对局 ID 及其别名的连通组划分 60% 检索库、20% 验证集、20% 固定测试集，来源模式 / 地图 / 已知 build 按组分层。",
             "先对全库冻结分区，再应用半径筛选；同一对局的别名和跨模式记录不会跨区。分区独立于圆心误差和评估成绩，尚未按测试结果调参。",
             "无源对局 ID 的样本数：" + str(result["missing_source_id_count"]) + "。内容去重已在入库时完成；指标按保存的样本计数，不按别名出现次数加权。", "",
             "| 范围 | 检索库 | 验证集 | 测试集 |", "| --- | ---: | ---: | ---: |"]
    for name, counts in result["cohort_split_counts"].items():
        lines.append(f"| {name} | {counts['library']} | {counts['validation']} | {counts['test']} |")
    lines += ["", "检索库限定相同地图标识和相同 build 值；主实验只检索 PUBLIC。build=null 只代表双方均未知，不能证明机制版本相同。候选按已有距离公式排序：圈次权重 1、2、4，半径平方差权重 0.25；去除完全相同目标圈的重复候选。", "",
              "## 主实验：PUBLIC、目标半径 728", "",
              "圆心误差单位为源站地图坐标（地图边长 16,384）。1536 像素底图上误差乘以 1536/16384。目标半径 728 相当于底图半径 68.25 像素。",
              "“Top-k 覆盖”表示前 k 个候选中至少一个圆心落入真实目标圈，不表示精确圆心命中、圆面积重叠率或胜率。缺少候选计为未覆盖；Top-5 最佳误差需要事后真实答案选择候选，不能当作可部署的预测误差。", "",
              "| 已知圈 | 测试数 | Top-1 中位误差 | P90 | P95 | 中位底图像素 | Top-1 覆盖 | Top-3 覆盖 | Top-5 覆盖 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for stage, metrics in main.items():
        error = metrics["overall"]["top1_center_error"]
        cov = metrics["overall"]["coverage"]
        lines.append(f"| 前 {stage} 圈 | {metrics['overall']['queries']} | {error['median']:.1f} | {error['p90']:.1f} | {error['p95']:.1f} | {error['median']*1536/COORD_SIZE:.1f} | {cov['1']:.1%} | {cov['3']:.1%} | {cov['5']:.1%} |")
    lines += ["", "### 与简单基线比较", "", "“最近已知圈圆心”直接使用输入的最后一个已知圈圆心；“历史平均圆心”仅用兼容检索库计算。", "",
              "| 已知圈 | 检索 Top-1 中位误差 / P90 | 最近已知圈圆心中位误差 / P90 | 最近已知圈圆心覆盖 | 历史平均圆心中位误差 |", "| --- | ---: | ---: | ---: | ---: |"]
    for stage, entry in main.items():
        m = entry["overall"]
        lines.append(f"| 前 {stage} 圈 | {m['top1_center_error']['median']:.1f} / {m['top1_center_error']['p90']:.1f} | {m['latest_known_center_error']['median']:.1f} / {m['latest_known_center_error']['p90']:.1f} | {m['latest_known_center_coverage']:.1%} | {m['historical_mean_center_error']['median']:.1f} |")
    lines += ["", "### 已见与未见的精确圈型", "", "按当前输入前缀是否在检索库逐字段完全相同分组；不同源对局的相同圈型允许出现，但单独报告。", "",
              "| 已知圈 | 分组 | 测试数 | Top-1 中位误差 | Top-5 覆盖 |", "| --- | --- | ---: | ---: | ---: |"]
    for stage, entry in main.items():
        for key, label in (("seen", "已见"), ("unseen", "未见")):
            m = entry[key]
            med = m["top1_center_error"]["median"]
            coverage = m["coverage"]["5"]
            if med is None:
                lines.append(f"| 前 {stage} 圈 | {label} | {m['queries']} | — | — |")
            else:
                lines.append(f"| 前 {stage} 圈 | {label} | {m['queries']} | {med:.1f} | {coverage:.1%} |")
    lines += ["", "## 标签与来源敏感性分析", "", f"全标签实验保留 {len(result['excluded_records'])} 条其他半径的 PUBLIC 样本；混合检索实验只向主实验的检索库加入 ALGS 半径 728 样本，查询仍为同一 PUBLIC 测试集。以下不能用来替代主实验或证明比赛与排位的机制一致。", "",
              "| 实验 | 已知圈 | 测试数 | Top-1 中位误差 | Top-5 覆盖 |", "| --- | --- | ---: | ---: | ---: |"]
    for name in ("public_all_labels", "public_r728_mixed_library"):
        for stage, entry in scenarios[name]["test"].items():
            m = entry["overall"]
            lines.append(f"| {name} | 前 {stage} 圈 | {m['queries']} | {m['top1_center_error']['median']:.1f} | {m['coverage']['5']:.1%} |")
    excluded_splits = ", ".join(sorted({r['split'] for r in result['excluded_records']})) or "无不同半径记录"
    lines += ["", f"不同半径记录所在分区：`{excluded_splits}`。敏感性差异由逐条查询与候选 ID 保存在 results.json 中；不能凭少量异常解释总体机制。",
              "", "## 验证集样本量探测", "", "以下只用验证集，采用固定种子生成嵌套的 PUBLIC 检索子集；未使用固定测试集选择参数。单次子集实验只能提示覆盖趋势，不能推算达到某个命中率需要的准确数据条数。", "",
              "| 检索样本 | 已知圈 | 验证数 | Top-1 中位误差 | Top-5 覆盖 |", "| --- | --- | ---: | ---: | ---: |"]
    for entry in result["validation_learning_curve"]:
        m = entry["metrics"]
        lines.append(f"| {entry['library_size']} | 前 {entry['stages']} 圈 | {m['queries']} | {m['top1_center_error']['median']:.1f} | {m['coverage']['5']:.1%} |")
    known_radius_text = "；".join(f"半径 {radius}：{count} 条" for radius, count in sorted(result['known_radius_counts']['3'].items()))
    lines += ["", "## 标签核查", "", "已核查的异常 / 冲突原始 JSONL 行号：" + ", ".join(str(n) for n in result['label_audit_raw_lines']) + "。原始目标和已知圈的差异已来自源站响应，不能归因于规范化时改变坐标。逐条返回值、行哈希、源对局 ID、批次和圈位见 label-audit.json。正式库与校验规则未修改。",
              f"第三个已知圈半径分布：{known_radius_text}。少见的已知圈半径不直接判错，主实验仍按目标半径选择；同一目标半径只是评估分层条件，不能证明内部圈次 / 游戏机制相同。",
              "圆心落入目标圈的指标存在几何上的宽容：已知第三圈半径通常约为目标圈半径的两倍，且正式库要求目标圈包含在已知圈内。因此第三圈圆心本身就容易落入目标圈；高覆盖不能代替准确圆心预测，应同时看误差与简单基线。",
              "源站玩法说明称目标为最后一个圈的圆心，但未给出内部圈次；不足以证明是梅花桩、不同版本或坏数据。[Ring Guessr 玩法说明](https://apexlegendsstatus.com/algs/ring-guessr)。此前回放接口触发限流 / 验证，本次没有重试该接口。", "",
              "## 复现与下一步", "", "```powershell", "& '.\\.venv\\Scripts\\python.exe' -m ringlab.evaluate", "& '.\\.venv\\Scripts\\python.exe' -m unittest discover -s tests -v", "```", "",
              "manifest.json 保存数据指纹、分区和别名；results.json 保存每次查询的候选 ID、误差及汇总；label-audit.json 保存标签证据。重新运行会使用同一规则生成相同分区与数值，生成时间不同。正式库 SHA-256 变化时属于新的评估版本，不能与本报告视为同一固定测试。",
              "本次验证集样本量探测中，多候选覆盖总体改善，首圈单候选误差没有单调改善。单次子集实验不支持给出达到高准确率所需的固定数据量，也不支持仅靠继续采集即可解决排序问题。",
              "下一步先在验证集改进候选排序，并与第三圈圆心基线比较，再建立手动圈位输入与候选地图展示，用真实截图检验识别误差。当前近邻排序不提供校准概率；机器学习也应先与本基线比较。本次固定测试已查看，后续若根据这些结果改设计，应另留新增独立对局作最终验收，不能反复用本测试集选择模型。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_FILE)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "evaluation")
    args = parser.parse_args()
    records = load_records(args.data)
    if not records:
        raise ValueError("Evaluation requires a nonempty dataset")
    split = make_split(records)
    assert_no_leakage(split)
    assigned = {record_id: group["split"] for group in split for record_id in group["record_ids"]}
    cohorts = {"all": records, "public_all_labels": [r for r in records if r["source_mode"] == "PUBLIC"],
               "public_r728": [r for r in records if r["source_mode"] == "PUBLIC" and r["final_ring"].get("r") == MAIN_RADIUS],
               "algs_r728": [r for r in records if r["source_mode"] == "ALGS" and r["final_ring"].get("r") == MAIN_RADIUS]}
    counts = {name: {part: sum(assigned[r["id"]] == part for r in cohort) for part in ("library", "validation", "test")} for name, cohort in cohorts.items()}
    fingerprint = hashlib.sha256(args.data.read_bytes()).hexdigest()
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "seed": SEED, "dataset_sha256": fingerprint,
              "coordinate_size": COORD_SIZE, "pixel_reference_size": 1536, "cohort_split_counts": counts,
              "missing_source_id_count": sum(not source_ids(r) for r in records),
              "excluded_records": [{"id": r["id"], "radius": r["final_ring"].get("r"), "split": assigned[r["id"]],
                                    "reason": "目标半径与主评估 728 标签不一致；来源未核实，保留在正式库与敏感性实验"}
                                   for r in records if r["source_mode"] == "PUBLIC" and r["final_ring"].get("r") != MAIN_RADIUS],
              "scenarios": {}, "validation_learning_curve": []}
    for scenario in ("public_r728", "public_all_labels", "public_r728_mixed_library"):
        queries_cohort = cohorts["public_r728" if scenario.endswith("mixed_library") else scenario]
        library_cohort = queries_cohort + cohorts["algs_r728"] if scenario.endswith("mixed_library") else queries_cohort
        library = [r for r in library_cohort if assigned[r["id"]] == "library"]
        scenario_result = {"library_count": len(library)}
        for part in ("validation", "test"):
            scenario_result[part] = {}
            queries = [r for r in queries_cohort if assigned[r["id"]] == part]
            for stages in (1, 2, 3):
                rows = evaluate_queries(library, queries, stages, mix_modes=scenario.endswith("mixed_library"))
                scenario_result[part][str(stages)] = {"overall": summarize(rows),
                    "seen": summarize([r for r in rows if r["exact_input_seen"]]),
                    "unseen": summarize([r for r in rows if not r["exact_input_seen"]]), "queries": rows}
        result["scenarios"][scenario] = scenario_result
    library_groups = [group for group in source_groups(cohorts["public_r728"]) if assigned[group[0]["id"]] == "library"]
    random.Random(SEED).shuffle(library_groups)
    validation = [r for r in cohorts["public_r728"] if assigned[r["id"]] == "validation"]
    for size in sorted({min(size, len(library_groups)) for size in (100, 200, 400, len(library_groups))}):
        subset = [r for group in library_groups[:size] for r in group]
        for stages in (1, 2, 3):
            result["validation_learning_curve"].append({"library_size": len(subset), "source_groups": size, "stages": stages,
                                                        "metrics": summarize(evaluate_queries(subset, validation, stages))})
    args.output.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output / "manifest.json", {"dataset_sha256": fingerprint, "seed": SEED,
                      "method": "source-ID alias connected groups; stratified 60/20/20; fixed before radius filtering",
                      "groups": split, "cohort_split_counts": counts, "excluded_records": result["excluded_records"]})
    labels = label_audit(records, ROOT / "data" / "raw" / "ringguessr-pairs.jsonl")
    result["label_audit_raw_lines"] = [item["line"] for item in labels["raw_evidence"]]
    result["known_radius_counts"] = labels["known_radius_counts"]
    write_json_atomic(args.output / "results.json", result)
    write_json_atomic(args.output / "label-audit.json", labels)
    (args.output / "EVALUATION_REPORT.md").write_text(render_report(result), encoding="utf-8")
    print(json.dumps({"counts": counts, "test": {stage: entry["overall"] for stage, entry in result["scenarios"]["public_r728"]["test"].items()}}, ensure_ascii=True))


if __name__ == "__main__":
    main()
