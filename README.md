# Apex 世界尽头最终圈研究

本地项目已建立可追溯的世界尽头圈位样本库，完成历史检索评估和首轮监督回归训练。本地网页第一版已可运行，已用一张真实游戏截图完成自动定位和两圈识别检查，更多截图场景待验收。

最新范围、已完成事项和后续步骤见 [PROJECT_PLAN.md](PROJECT_PLAN.md)。

想先了解项目做了什么、有哪些模块以及各模块对应的文件夹，请阅读 [项目概览与模块说明](PROJECT_OVERVIEW.md)。

**GitHub 版本管理（2026-10-13）：** 私有仓库 [qiiiiii4869/apex-ringlab](https://github.com/qiiiiii4869/apex-ringlab)。仓库保存源码、前端、模型、正式数据、测试与文档；本地虚拟环境、原始采集、缓存、日志、临时输出和部署连接记录不提交。文件用途见 [FILE_GUIDE.md](FILE_GUIDE.md)。`.gitattributes` 保留文件原始字节，避免换行转换改变训练清单中的 SHA-256；不要对正式库和模型做无意义的格式重写。

**服务与并发优化（2026-10-13）：** FastAPI + Uvicorn 已部署到 Ubuntu ECS，仍只监听服务器本机。固定依赖、有限工作池 / 排队、限流、超时、来源和隐私日志检查通过；SIFT 精确匹配改为分块矩阵计算。Windows / Linux 各 65 项 Python 测试通过，用户本地网页手动验收通过。目标服务器两人识图最长约 5.9 秒（优化前约 26.5 秒），四人同时识图全部成功、最长约 10.9 秒；这些仅为已测截图结果。域名 `codeqiqi.com` 已购买且用户确认实名通过，备案 / HTTPS 和目标浏览器验收待完成。部署和回退说明见 [DEPLOYMENT.md](DEPLOYMENT.md)。

**最新状态（2026-10-12）：** 总量 1,000 条的采集目标已完成，最终保存 1,001 条（PUBLIC 排位 967、ALGS 34），16 条异常响应单独隔离。采集器和本地后台监控已正常退出，半小时定时任务 `apex` 已暂停。已核查目标冲突的原始响应，并完成 194 条独立 PUBLIC 对局检索评估。前三圈前五候选覆盖 94.3%，第一候选覆盖 59.8%，当前排序需改进。首轮训练比较 Ridge、ExtraTrees 和梯度提升，三个圈数均选择 ExtraTrees（200 棵树）。前三圈模型在 193 条验证样本上平均误差为 459.9，历史检索第一候选为 596.1。完整指标见 [评估报告](data/evaluation/EVALUATION_REPORT.md) 和 [训练报告](data/training/TRAINING_REPORT.md)。详见 [数据说明](data/DATASET.md) 和 [交接入口](HANDOFF.md)。

## 环境

Windows PowerShell 7、CPython 3.13，推荐训练使用的 3.13.13。现有 `.venv` 可直接使用。重新安装使用独立环境与固定依赖：

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

## 本地网页

```powershell
& '.\scripts\start-web.ps1'
```

打开 [本地圈位实验室](http://127.0.0.1:8765/)，点击“载入示例 → 在地图上预测”即可检查环境。也可以手动输入一至三个连续圈，或在地图上选择三个边界点校正。页面将模型与历史圈型合并为最多 5 个结果，每项显示历史误差推导的估计命中概率。默认展开所选圈，其余为编号定位点，可切换候选或叠加全部预测圈。

同一局首圈采用后，点击“继续上传本局截图”补充第 2 / 3 圈，新图不必包含旧圈。旧圈会保留并合并预测，可开启“叠加本局已知圈”一起查看。圈位保存在当前标签页，刷新后可恢复；图片不持久保存。另一把游戏先点击“开始新对局”清空记录。当前最多支持前三圈。

截图导入支持 JPG / PNG、最大 8 MB。自动定位与圆弧识别是试验功能，失败时可框选完整地图并手动取点，圈次必须确认。默认本地运行时仅在本机内存中处理；将来按 HTTPS 配置部署后，图片在服务器内存中临时处理。两种模式都不保存图片、不进入训练库，页面自动说明实际处理方式。已验证用户提供的一张真实截图及缩小 JPEG 变体；更多场景仍待验证。

详细步骤、运行范围和 QA 限制见 [网页使用说明](WEB_GUIDE.md)。保持服务运行才能访问；`-Port 8766` 可以选择其他端口。历史参考库固定为 579 条训练排位记录，不把验证 / 测试样本临时回灌。

## 数据采集

在项目目录执行：

当前总量已经超过 1,000，下面的原目标命令不会继续请求数据；仅在用户明确要求扩大样本库时设置更大的目标。

```powershell
& '.\scripts\collect-ringguessr.ps1' -Target 1000 -MaxGames 100 -DelaySeconds 2 -Mode PUBLIC
```

- `Target`：正式样本库的目标总条数，不是本次新增条数。达到目标后会完成当前 10 轮再结束会话，最终数量可能略超目标。
- `MaxGames`：本次最多进行多少组游戏，每组最多 10 轮。
- `DelaySeconds`：请求之间的间隔，默认 1.5 秒。
- `Mode`：`PUBLIC`、`ALGS` 或 `BOTH`；`BOTH` 交替采集两类来源。
- `MaxRecoveries`：可恢复错误的最大连续恢复次数，默认 5 次，设为 0 可禁用；旧参数名 `MaxServerRecoveries` 仍作为别名兼容。普通接口错误、HTTP 408 / 5xx、网络超时、缺失配对字段和回合超时会丢弃当前会话，再创建新的访客会话，不在旧游戏内重放可能已执行的 POST。成功取得配对后重置连续失败计数。
- `RecoveryDelaySeconds` / `MaxRecoveryDelaySeconds`：恢复等待时间，默认从 30 秒开始逐次翻倍，上限 300 秒。
- 只保存世界尽头配对样本。其他地图按游戏正常流程完成该轮，但不入库。
- 采集使用新访客会话，固定点击地图中心；不尝试优化猜圈游戏分数。
- 已知圈和最终圈来自同一会话同一轮，不要求完整的中间圈序列。
- 会话 token 和 Cookie 不写入数据或日志。
- HTTP 401 / 403 / 429、验证码、JSON 或 HTML 中的访问限制 / 限流提示立即停止；普通非 JSON 接口响应允许按上述上限恢复。连续失败超出恢复次数、数据写入或校验程序出错也会停止。圈位校验不通过的配对响应单独隔离，不进入正式库。
- 每个世界尽头样本取得后立即落盘、校验和入库；再次运行会保留已有样本并去重。
- 正式库、隔离文件和导入报告以临时文件原子替换保存。Windows 暂时拒绝替换（错误 5 / 32 / 33）时最多尝试 8 次，等待 0.05～0.5 秒；替换成功前保留原文件，永久权限或其他写入故障仍停止。
- 单个采集进程写入数据。不要同时启动两个采集器。

用户于 2026-10-11 确认 `PUBLIC` 属于排位，可用于本项目。PUBLIC 统一标记为 `ranked`，ALGS 标记为 `tournament`；确认依据保存在 `data/source-modes.json` 和每条记录的 `game_mode_evidence` 中。优先追加排位来源可使用 `-Mode PUBLIC`。

曾按总量目标 1,000 条启动 PUBLIC 后台续采，收工时主动暂停在 340 条。`data/collection-watch.json` 保存监控进程与采集进程 ID，暂停后这些 ID 仅作历史记录，操作进程前必须再次核对身份。`scripts/watch-ringguessr-collection.ps1` 运行时每 30 秒更新数据说明，并只在采集正常达到单批组数上限时串行启动下一批。可恢复错误在采集器内自动重新开始会话；超出恢复上限或遇到访问限制的失败批次不会被本地监控重新启动，连续一批没有新增样本也会停止；额外续采最多 9 批，每批最多 100 组。采集器使用进程互斥锁拒绝重复启动。恢复后台采集的命令见 `HANDOFF.md`；应用内定时任务 `apex` 需要单独恢复。进程依赖本机持续运行。

## 数据文件

| 文件 | 用途 |
| --- | --- |
| `data/rings.json` | 校验、去重后的正式世界尽头样本 |
| `data/raw/ringguessr-pairs.jsonl` | 配对原始响应，便于追溯与重新导入 |
| `data/collection-progress.json` | 最新采集批次的轮数、数量、停止原因 |
| `data/collection-watch.json` | 后台监控状态、进程 ID 和续采批次数 |
| `data/monitor-checkpoint.json` | 定时检查基准及主动暂停状态 |
| `data/handoff-snapshot.json` | 本次收工的固定统计快照 |
| `data/completion-snapshot.json` | 本轮 1,000 条目标的完成统计 |
| `data/final-ring-conflicts.json` | 相同前三圈与不同目标标签的详细样本 |
| `data/collection-report.json` | 正式库来源统计、版本统计和首圈冲突审计 |
| `data/quarantine-records.json` | 未通过校验的原始配对响应和原因 |
| `data/DATASET.md` | 人类可读的本批数据说明 |

原始响应保存在被 Git 忽略的 `data/raw/` 下；正式样本库和说明保留在项目中。

圈位不满足当前嵌套校验条件时会被隔离，这不等于已经证明源站数据错误，后续需要核实机制与字段含义。重新生成当前统计说明可执行 `& '.\.venv\Scripts\python.exe' -m ringlab.report`。

从原始响应重新校验和增量导入：

```powershell
& '.\.venv\Scripts\python.exe' -m ringlab.ingest 'data\raw\ringguessr-pairs.jsonl'
```

默认导入在发现异常时返回非零退出码，但会保存通过校验的记录。批量采集使用 `--allow-quarantine`，保留异常记录并继续其他正常对局。

样本 ID 由地图标识、来源模式、已知圈和最终圈坐标共同生成。重复圈型不重复入库，但保留能取得的多个源对局 ID。ALGS 与 PUBLIC 分开去重；不同模式中的相同对局仍需在后续评估时分到同一组。

“最终圈”当前指源站 `finalRing`，内部圈次尚未确认，`stage` 保留为 `null`。服务端 build 未知，不能把地图标识或采集日期当作游戏版本。

## 检查

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '.\tests\test-collector-modes.ps1'
& '.\tests\test-collector-recovery.ps1'
& '.\.venv\Scripts\python.exe' -c "from ringlab.data import load_records; from ringlab.retrieval import audit; print(audit(load_records()))"
```

测试中的坐标是独立测试夹具，不会写入正式样本库。46 项 Python 测试及 6 项前端几何检查通过；已有独立对局检索评估，尚未验证真实截图。

## 独立对局评估

```powershell
& '.\.venv\Scripts\python.exe' -m ringlab.evaluate
```

按所有源对局 ID 与别名分组，固定 60% 检索 / 20% 验证 / 20% 测试。主实验只使用目标半径 728 的 PUBLIC 数据，579 / 193 / 194 条；异常半径记录保留并单独做敏感性分析。`data/evaluation/manifest.json` 保存数据指纹和分区，`results.json` 保存逐条候选及统计，`label-audit.json` 保存冲突原始响应证据。正式库不被评估命令修改。

覆盖指候选圆心落入真实源站目标圈，不能当作精确圆心预测率。前三圈直接用第三圈圆心的单点覆盖为 89.7%，高于当前检索第一候选的 59.8%。已完成首轮回归训练，手动圈位网页已接入，下一步验证真实游戏截图；本测试已查看，最终模型验收另留新增独立对局。

## 模型训练与推理

```powershell
& '.\.venv\Scripts\python.exe' -m ringlab.train
& '.\.venv\Scripts\python.exe' -m ringlab.model 'data\training\example-query.json'
```

使用 579 条 PUBLIC、目标半径 728 的训练样本。九种配置仅在训练内部 5 折源对局分组交叉验证选择，再对固定 193 条验证数据比较；旧 194 条测试数据不参与本轮训练、选型或评分。训练模型学习相对最后一个已知圈的圆心偏移，三个圈数分别保存至 `models/stage-N.joblib`。验证集没有加入拟合。

`data/training/manifest.json` 记录数据与分区指纹、参数、版本及模型哈希；`stage-N-selection.json` 保存折外预测与选型依据；`results.json` 保存逐条验证结果。推理只需已知圈及地图 / build / 来源上下文，拒绝不同地图、build、模式或不匹配圈次。示例不包含最终圈标签。

前三圈模型验证圈内覆盖 86.0%，直接用第三圈圆心为 93.8%；模型平均误差更低，但不代表所有指标胜出。首圈模型圈内覆盖仅 11.4%，仍不足以精确猜圈。详细比较见 [首轮训练报告](data/training/TRAINING_REPORT.md)。

数据源：[Apex Legends Status Ring Guessr](https://apexlegendsstatus.com/algs/ring-guessr)。
