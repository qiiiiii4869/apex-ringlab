"""Write a reproducible, human-readable collection snapshot."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from .data import DATA_FILE, ROOT, load_records
from .retrieval import audit


def main():
    records = load_records()
    result = audit(records)
    counts = Counter(r["source_mode"] for r in records)
    versions = Counter(r["map_version"] for r in records)
    radii = Counter("未知" if r["final_ring"].get("r") is None else str(r["final_ring"]["r"]) for r in records)
    radius_lines = "\n".join(f"| {radius} | {count} |" for radius, count in sorted(radii.items()))
    game_ids = {game_id for r in records for game_id in ([r.get("source_game_id")] + r.get("source_game_ids", [])) if game_id}
    progress_path = ROOT / "data" / "collection-progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    raw_path = ROOT / "data" / "raw" / "ringguessr-pairs.jsonl"
    raw_count = sum(bool(line.strip()) for line in raw_path.read_text(encoding="utf-8-sig").splitlines()) if raw_path.exists() else 0
    quarantine_path = ROOT / "data" / "quarantine-records.json"
    quarantine = json.loads(quarantine_path.read_text(encoding="utf-8")) if quarantine_path.exists() else []
    quarantine_count = len(quarantine)
    quarantine_reasons = Counter(item["reason"] for item in quarantine)
    reason_lines = "\n".join(f"| {reason} | {count} |" for reason, count in sorted(quarantine_reasons.items())) or "| 无 | 0 |"
    instant = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S +08:00")
    version_lines = "\n".join(f"| `{version}` | {count} |" for version, count in sorted(versions.items()))
    conflict_text = "\n".join(f"- {', '.join(group)}" for group in result["conflict_examples"]) or "当前没有发现样本内冲突。"
    evaluation_path = ROOT / "data" / "evaluation" / "results.json"
    evaluation_text = "尚未完成独立对局效果评估。下一步按所有源对局 ID 及别名分组留出评估样本，比较一至三圈输入；同一对局不能进入不同数据分区。"
    if evaluation_path.exists():
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        if evaluation.get("dataset_sha256") == hashlib.sha256(DATA_FILE.read_bytes()).hexdigest():
            metrics = evaluation["scenarios"]["public_r728"]["test"]
            cohort = evaluation["cohort_split_counts"]["public_r728"]
            rows = "\n".join(f"| 前 {stage} 圈 | {item['overall']['queries']} | {item['overall']['coverage']['1']:.1%} | {item['overall']['coverage']['5']:.1%} | {item['overall']['top1_center_error']['median']:.1f} |" for stage, item in metrics.items())
            evaluation_text = f"""已完成按所有源对局 ID 及别名分组的独立评估。主实验使用目标半径 728 的 PUBLIC 样本：{cohort['library']} 条检索库、{cohort['validation']} 条验证、{cohort['test']} 条固定测试，分区与正式库 SHA-256 保存在 `data/evaluation/manifest.json`。

| 已知圈 | 测试数 | 第一候选覆盖 | 前五候选覆盖 | 第一候选圆心中位误差 |
| --- | ---: | ---: | ---: | ---: |
{rows}

覆盖指候选圆心落入真实源站目标圈，误差单位为 0～16384 地图坐标。前三圈直接使用第三圈圆心的单点覆盖为 {metrics['3']['overall']['latest_known_center_coverage']:.1%}，高于当前检索第一候选；不能把前五候选覆盖当成精确预测率。评估使用准确坐标，尚未验证截图误差。

不同半径样本保留在正式库，单独做全标签敏感性分析。原始响应证据见 `data/evaluation/label-audit.json`；内部目标圈次仍未核实。完整指标、基线、来源敏感性和验证集样本量探测见 [独立对局评估报告](evaluation/EVALUATION_REPORT.md)。

后续模型改进与手动圈位 / 截图网页流程须分别验证；本次固定测试已查看，后续设计变更需另留新增独立对局验收。"""
        else:
            evaluation_text = "已有历史评估，但其数据指纹与当前正式库不同；请重新评估，不能沿用历史指标。"
    training_text = "尚无回归模型训练结果。"
    training_path = ROOT / "data" / "training" / "results.json"
    if training_path.exists():
        training = json.loads(training_path.read_text(encoding="utf-8"))
        if training.get("dataset_sha256") == hashlib.sha256(DATA_FILE.read_bytes()).hexdigest():
            training_rows = "\n".join(f"| 前 {stage['stages']} 圈 | {stage['config']['family']} | {stage['validation_count']} | {stage['validation']['learned']['metrics']['center_error']['mean']:.1f} | {stage['validation']['learned']['metrics']['center_error']['median']:.1f} | {stage['validation']['learned']['metrics']['circle_coverage']:.1%} |" for stage in training["stages"])
            training_text = f"""已完成监督回归模型训练，学习最终圈相对最后已知圈的圆心偏移。只使用 {training['train_count']} 条 PUBLIC 训练样本，以训练内部 5 折分组交叉验证选择参数，再对 {training['validation_count']} 条验证样本评分。旧测试集未用于本轮训练、选型或评分；最终验收仍需新增独立对局。

| 输入 | 胜出模型 | 验证数 | 平均圆心误差 | 中位误差 | 圈内覆盖 |
| --- | --- | ---: | ---: | ---: | ---: |
{training_rows}

三个模型已保存在 `models/stage-1.joblib`、`stage-2.joblib`、`stage-3.joblib`。验证指标不能称作最终测试准确率；第三圈圆心基线仍有更高的宽松圈内覆盖，但训练模型平均误差更低。完整基线对照、较小误差阈值和算法说明见 [训练报告](training/TRAINING_REPORT.md)。"""
        else:
            training_text = "已有历史训练模型，但数据指纹与当前正式库不同；模型状态需重新核查，不能沿用历史指标。"
    if "max_recoveries" in progress:
        recovery_policy = f"可恢复错误最多连续恢复 {progress['max_recoveries']} 次；初始等待 {progress.get('recovery_delay_seconds', 30)} 秒，逐次翻倍，最多等待 {progress.get('max_recovery_delay_seconds', 300)} 秒。成功配对后重置连续失败计数。HTTP 401 / 403 / 429 和验证要求不恢复。"
    else:
        recovery_policy = "旧批次策略：仅 HTTP 5xx 最多恢复 2 次，每次等待 10 秒；403 / 429 不恢复。"
    text = f"""# 世界尽头配对样本说明

统计时间：{instant}（北京时间）。这是生成时的快照，继续采集后可重新生成。

## 样本规模

| 指标 | 数量 |
| --- | ---: |
| 去重后的已知圈＋最终圈样本 | {len(records)} |
| PUBLIC 来源 | {counts['PUBLIC']} |
| ALGS 来源 | {counts['ALGS']} |
| 可追溯的不同源对局 ID | {len(game_ids)} |
| 按用户确认标记的排位样本 | {sum(r['game_mode'] == 'ranked' for r in records)} |
| 世界尽头原始配对响应（含最初探测样本） | {raw_count} |
| 未通过当前校验、单独隔离的响应 | {quarantine_count} |
| 去重时合并的重复配对响应 | {max(0, raw_count - quarantine_count - len(records))} |

| 地图标识 | 样本数 |
| --- | ---: |
{version_lines}

## 采集方法

数据源：[Apex Legends Status Ring Guessr](https://apexlegendsstatus.com/algs/ring-guessr)。

地图识别依据是接口的 `map` 字段，采集器仅保留 `mp_rr_desertlands` 开头的记录。已按源对局 ID `2e19755b83ff412fb59fd13061c99f17` 与官方比赛列表交叉核对，页面标题为 `B vs. D - Game #5 - World's Edge`。证据保存在 `data/map-identification.json`，不是仅凭圈位或目测猜测地图。

同一访客会话、同一轮依次请求已知圈和提交猜测后的 `finalRing`。已知圈含圆心、半径和圈次；最终圈保留圆心、源站返回的半径及 `ringguessr_final` 标签。未获取中间第 4 圈，也未从其他回放拼接标签。

`data/rings.json` 为校验后的正式库，`data/raw/ringguessr-pairs.jsonl` 保留配对原始响应。根据地图、来源模式、已知圈和最终圈坐标去重。已确认的重复圈型保留可用源对局 ID，冲突最终圈保留为不同样本。数据中的 ID `rg_...` 是内容哈希，不代表源站对局 ID。

异常响应保存在 `data/quarantine-records.json`。嵌套与包含关系是目前采用的几何校验条件；不通过校验不等于已经证明源数据错误，仍需核实比赛机制和源站字段含义。这些响应暂不进入正式库。

| 隔离原因 | 响应数 |
| --- | ---: |
{reason_lines}

单一来源模式参数曾被脚本错误拆成首字母，产生了两条模式不明的响应；已通过来源校验隔离，正式库未受影响。参数处理现已修复并增加 PUBLIC / ALGS / BOTH 三种选择的回归检查。

## 首圈与最终圈的样本审计

- 分组后的不同首圈：{result['unique_first_rings']}。
- 出现多个不同样本的重复首圈组：{result['repeated_first_ring_groups']}。
- 相同首圈对应不同最终圈的冲突组：{result['conflict_groups']}。

{conflict_text}

审计按地图标识、来源模式及可用 build 分组。完全重复的圈型在入库时已经去重，因此重复首圈统计不等于原始重复抽取次数。该审计只描述当前样本，不能证明服务器刷圈逻辑。

## 目标圈标签审计

| 源站返回的目标圈半径 | 样本数 |
| --- | ---: |
{radius_lines}

不同半径需要核实是否对应相同内部圈次。当前 `stage` 仍为 `null`，不把半径差异自动解释成数据错误或不同游戏机制。相同已知圈对应不同目标的记录继续保留。详细冲突记录见 `data/final-ring-conflicts.json`；原始响应核查与评估分层政策见 `data/evaluation/label-audit.json`（如已生成）。

## 独立对局效果评估

{evaluation_text}

## 机器学习训练状态

{training_text}

## 最新采集批次

- 批次 ID：`{progress.get('batch_id', 'initial-probe')}`。
- 状态：`{progress.get('status', 'unknown')}`。
- 本批目标总样本数：{progress.get('target', 100)}。
- 本批来源选择：`{progress.get('source_mode', 'BOTH')}`。
- 已启动游戏组数：{progress.get('games', 0)}（最后一组可能未完成）。
- 已完成轮数：{progress.get('rounds', 0)}。
- 世界尽头原始配对响应：{progress.get('worlds_edge_pairs', 0)}。
- 跳过的其他地图轮数：{progress.get('other_maps', 0)}。
- 停止原因：{progress.get('stop_reason') or '无'}。
- 自动恢复次数：{progress.get('recoveries', progress.get('server_recoveries', 0))}（其中 HTTP 5xx：{progress.get('server_recoveries', 0)}）。
- 连续恢复次数：{progress.get('consecutive_recoveries', '旧批次未记录')}。
- 恢复策略：{recovery_policy}

本批总量目标 {progress.get('target', 100)} 条{"已达到" if len(records) >= progress.get('target', 100) else "尚未达到"}。最新批次若在 `endGame` 收尾阶段报错，已经入库的配对样本不受影响。脚本按网站流程完成当前 10 轮后再结束会话，最终数量可能略超目标。

批次计数不包含最初的单轮探测样本。正式库数量经过跨批次去重，不一定等于本批取得的世界尽头响应数。

## 使用限制与后续工作

- 用户于 2026-10-11 确认 PUBLIC 来源属于排位，可用于本项目；已标记为 `ranked`，确认依据保存在 `data/source-modes.json` 和每条样本的 `game_mode_evidence` 中。ALGS 标记为比赛数据。
- 游戏发生时间与服务端 build 尚未获得；采集时间不能替代这些字段。
- 地图标识为源站返回值，尚未确认与当前排位版本完全一致。
- 最终圈内部圈次尚未核实，`stage` 为 `null`；它当前仅指源站揭晓的目标圈。
- 历史检索基线不涉及模型训练；回归训练状态见上方。两者均未校准预测概率。
- 本地手动圈位网页与测试图链路已实现，使用方法与本轮验证见 `WEB_GUIDE.md`。真实游戏截图定位 / 识别和端到端视觉验收仍未完成；历史源站样本效果不能直接当作当前排位实战效果。

重新生成本说明：

```powershell
& '.\\.venv\\Scripts\\python.exe' -m ringlab.report
```
"""
    (ROOT / "data" / "DATASET.md").write_text(text, encoding="utf-8")
    print(json.dumps({"count": len(records), "source_modes": dict(counts), "audit": result}, ensure_ascii=True))


if __name__ == "__main__":
    main()
