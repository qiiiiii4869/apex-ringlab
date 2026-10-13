# 项目文件说明

核对日期：2026-10-13（北京时间）。本说明针对实际本地项目目录，不代表服务器目录实时状态。
后续版本管理更新：项目已初始化 Git 并创建私有仓库 `qiiiiii4869/apex-ringlab`，新增 `.gitattributes` 保留原始文件字节；下面的目录数量为生成说明时、初始化 Git 前的快照，不包含后来新增的 Git 元数据。完整 HTML / CSV 和 outputs 材料仅保留在本机，未提交 GitHub。
本次快照共有 **15,761 个文件、1,881 个子目录**（另列根目录）。去掉两个虚拟环境与字节码缓存后，列出 **229 个项目 / 工作材料文件**。
说明依据：项目源码结构、入口引用、JSON 字段、发布白名单和既有验收材料。第三方环境内部文件按所属包、目录和文件类型分类，未逐行审读或确认每个内部函数；完整清单明确标注依据。未读取部署连接记录内容，没有加载或重训模型，没有执行采集、服务、远程操作或清理。
完整文件与文件夹清单：[可搜索 HTML](outputs/project-file-inventory.html)、[CSV](outputs/project-file-inventory.csv)。HTML 无外部依赖，在浏览器直接打开即可，包含所有实际路径。生成文档本身的大小留空，避免自引用循环。ZIP / tar / wheel 作为一个实际文件计数，压缩包里的虚拟条目不作为已解压文件重复计数。

## 如何连起来工作

游戏截图 → web/app.js 上传 → ringlab/server.py 接收和排队 → workbench.py 调用 vision.py / matching.py 识圈 → 用户确认 → model.py 模型推理 + retrieval.py 历史检索 → probability.py 合并与估计 → 网页画出候选圈。
另一条离线路径是：采集脚本 → raw/ringguessr-pairs.jsonl → ingest.py / data.py → rings.json → evaluate.py 固定分区 → train.py → models 与 training 清单。网页访客上传不会自动走这条训练路径。

## 文件夹用途

| 文件夹 | 用途 |
| --- | --- |
| `./` | 整个项目根目录：文档、源码、数据、模型、测试、环境与部署材料的共同入口。 |
| `.venv/` | 日常开发使用的 Python 3.13 虚拟环境；pyvenv.cfg 显示允许读取系统级包，因此它并非完全独立的依赖集合。 |
| `ringlab/` | Python 后端与算法源码：截图识别、圈位推理、历史检索、概率估计、数据处理、训练和服务。 |
| `ringlab/__pycache__/` | Python 自动生成的字节码缓存；对应同名 .py 源文件，作用是加快模块加载。 |
| `web/` | 浏览器端页面、交互、几何计算和本局会话管理。 |
| `web/assets/` | 世界尽头地图底图；网页与截图识别使用 JPG，PNG 保留源图。 |
| `models/` | 训练得到的三个二进制模型，按已知圈数选择；不是图片或源代码。 |
| `data/` | 正式样本、来源证据、状态快照、训练与评估结果以及验收报告。 |
| `data/cache/` | 研究源站接口时保留的探测响应和源站前端 JavaScript；不是当前网页缓存。 |
| `data/raw/` | 未清洗的配对响应、外部参考包和历史采集日志；用于追溯，不是网页上传图片仓库。 |
| `data/raw/collection-batches/` | 以前采集批次的状态归档，保留暂停、故障、用户停止和达到目标的记录。 |
| `data/raw/checkpoints/` | 采集阶段的完整交接及完成快照 ZIP，用于恢复和校验历史状态。 |
| `data/evaluation/` | 历史检索的独立对局分区、标签核查、原始指标和可读评估报告。 |
| `data/training/` | 监督回归模型的分区、选型、版本、指纹、验证指标和无答案输入示例。 |
| `deploy/` | Linux 内部运行、正式 HTTPS 运行的 Compose 文件和反向代理示例。 |
| `scripts/` | 项目长期保留的采集、启动、压测、依赖固定、打包和远程部署辅助脚本。 |
| `tests/` | 项目自己的自动回归测试；Python、JavaScript 与 PowerShell 各测不同环节。 |
| `tests/fixtures/` | 固定测试素材，仅供回归测试，不进入模型训练。 |
| `tests/__pycache__/` | Python 测试模块的自动字节码缓存。 |
| `outputs/` | 开发与部署过程产生的发布包、备份、图片、日志和本次文件说明清单。 |
| `outputs/backups/` | 关键源码改造前的 ZIP 备份。 |
| `outputs/releases/` | 可交付发布包，以及 Docker Hub 不通时使用的官方 Python 镜像离线包。 |
| `outputs/qa/` | 开发、性能分析、部署验收的工作材料；其中不少脚本包含历史路径或容器 ID。 |
| `outputs/qa/clean-runtime/` | 为验证固定依赖能在全新环境安装而建立的第二个虚拟环境；不读取系统级包，不是云服务器或生产网站。 |
| `outputs/qa/linux-wheels/` | 用于 Linux x86_64 / CPython 3.13 离线安装的固定依赖 wheel 包；Windows 环境不使用这些安装包。 |
| `outputs/qa/python-base-blobs/` | 下载官方 Python Docker 镜像时缓存的配置及镜像层；包含压缩 blob 与解压后的层 tar。 |

## 所有项目文件逐项说明

下面每个项目文件单独列一行；同类批次日志也没有省略。体积是本次快照的字节数，不是所占磁盘分配空间。

### 根目录

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [.gitattributes](.gitattributes) | — | 保留原始文件字节，覆盖全局换行自动转换，保护正式库与模型的 SHA-256 校验一致性。 |
| [.dockerignore](.dockerignore) | 287 | Docker 构建白名单：只允许运行所需源码、JPG 底图、模型和指定数据进入构建上下文；原始采集、测试截图、环境和 outputs 默认排除。 |
| [.gitignore](.gitignore) | 63 | Git 忽略规则：环境、字节码、原始数据、缓存、输出和日志等不作为普通源码提交。文件存在不代表当前目录已初始化 Git 仓库。 |
| [1.png](1.png) | 2186844 | 根目录的游戏地图示例图片，能看到大圈及小圈。当前服务入口、前端和发布白名单未引用它；保留作人工参考。 |
| [2.png](2.png) | 1800751 | 根目录另一张游戏地图示例图片，含缩小安全区、伤害区、标记和游戏字幕。当前运行入口未引用，不自动进入训练数据。 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 13451 | 部署与回退操作说明：固定 Python 依赖、环境变量、容器资源、内部运行、正式域名 HTTPS 与验收流程。 |
| [Dockerfile](Dockerfile) | 1210 | 容器镜像构建步骤：基于固定 Python 3.13.13 Debian slim，安装图像系统依赖与 Python 锁定包，复制运行材料，以非 root 身份启动服务。提供可选镜像源 / 离线安装参数。 |
| [FILE_GUIDE.md](FILE_GUIDE.md) |  | 本次生成的项目文件说明：逐项解释项目文件，并介绍依赖环境和完整清单的阅读方法。 |
| [HANDOFF.md](HANDOFF.md) | 28755 | 接续工作的交接文档：当前运行版本、路径、已经验证的事项与后续工作。也记录采集暂停、历史测试集已经查看等约束。 |
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | 42168 | 项目计划书：需求、技术路线、里程碑、已完成证据和待办。顶部记录最新域名、部署与并发进度；下方保留历史，不应把旧状态当成当前状态。 |
| [README.md](README.md) | — | 项目概览与模块说明：介绍项目做了什么、八个模块及对应目录。与 PROJECT_OVERVIEW.md 对调后，作为 GitHub 首页展示文档。 |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | — | 原 README 内容：安装、启动、常用命令、采集及研究结果。已与 README.md 对调，两份文档的互相引用同步更新。 |
| [requirements-dev.txt](requirements-dev.txt) | 88 | 开发和验收依赖：先包含运行锁定清单，再添加 httpx、httpcore、certifi、psutil，用于接口测试与资源监测。 |
| [requirements.lock.txt](requirements.lock.txt) | 623 | 运行依赖及精确版本清单，含数值计算、机器学习、图像识别、FastAPI / Uvicorn 等；模型加载依赖这些版本。Windows 专用依赖带平台条件。 |
| [requirements.txt](requirements.txt) | 25 | 安装入口，只引用 requirements.lock.txt；pip install -r requirements.txt 会安装固定的运行依赖。 |
| [WEB_GUIDE.md](WEB_GUIDE.md) | 8655 | 网页使用说明：上传地图截图、确认圈次、手动校正、继续上传本局、预测、候选图层与当前能力边界。 |

### data

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [collection-progress.json](data/collection-progress.json) | 687 | 最新采集批次状态：批次、目标、游戏数、有效样本、恢复记录与停止原因。采集已完成，此文件不是正在运行的证明。 |
| [collection-report.json](data/collection-report.json) | 1627 | 最新导入统计：新增、重复、其他地图、异常、来源和首圈 / 目标冲突审计。 |
| [collection-watch.json](data/collection-watch.json) | 430 | 采集监控状态：监控 / 采集器 PID、目标、追加批次和停止 / 暂停信息。历史 PID 不代表仍有进程。 |
| [completion-backup.json](data/completion-backup.json) | 320 | 最终采集备份的路径、文件清单与 SHA-256，用于确认完成检查点归档完整。 |
| [completion-snapshot.json](data/completion-snapshot.json) | 906 | 达到 1000 目标后的最终完成快照：1001 条、来源计数、原始响应数、隔离与重复数量、暂停状态。 |
| [concurrency-four-clients.json](data/concurrency-four-clients.json) | 1638 | 并发优化后的云服务器四人同时使用场景与突发压测汇总。 |
| [concurrency-overload.json](data/concurrency-overload.json) | 290 | 五个同时识图请求的过载验收：四个成功 / 一个 503、最大任务占用、期间健康 / 预测响应及恢复。 |
| [concurrency-two-clients.json](data/concurrency-two-clients.json) | 1634 | 并发优化后的云服务器两人场景及连续突发压测原始汇总：成功数、耗时、CPU / RSS 和最终健康状态。 |
| [concurrency-validation.json](data/concurrency-validation.json) | 4085 | 本轮并发优化综合报告：前后耗时、两人 / 四人 / 超容量结果、回归、模型与数据指纹、运行限制、部署及发布包信息。 |
| [DATASET.md](data/DATASET.md) | 7792 | 由 report.py 生成的人类可读样本说明：规模、采集方法、来源、标签问题、评估、训练和限制。它是生成时快照，个别旧验收文字可能未反映最新状态。 |
| [deployment-validation.json](data/deployment-validation.json) | 2609 | FastAPI 迁移后的 Windows 本机服务和并发报告；包含 CPU / 内存、接口结果及检查范围，不代表云服务器性能。 |
| [final-ring-conflicts.json](data/final-ring-conflicts.json) | 2386 | 相同已知圈对应不同目标圈的审计材料，记录冲突样本和解释边界，避免静默删除有矛盾的数据。 |
| [handoff-snapshot.json](data/handoff-snapshot.json) | 862 | 较早一次交接时的采集快照，当时正式库为 340 条；保留历史，不是当前样本数。 |
| [map-identification.json](data/map-identification.json) | 739 | 世界尽头地图身份依据：源站地图 ID、源对局与官方比赛标题对应、底图来源，以及当前排位版本尚未核实的状态。 |
| [monitor-checkpoint.json](data/monitor-checkpoint.json) | 906 | 监控最后检查点，用于对比新增数量并记录目标完成与自动任务暂停状态。 |
| [quarantine-records.json](data/quarantine-records.json) | 20182 | 16 条未通过当前几何 / 来源规则的异常响应，保留原因供核查，不进入正式库；隔离不等于证明源数据错误。 |
| [rings.json](data/rings.json) | 1502140 | 正式去重样本库，目前 1001 条；每条包含已知圈、同轮揭晓目标、地图版本及来源信息。模型、历史检索与校验都依赖它，不是用户上传记录。 |
| [server-validation.json](data/server-validation.json) | 3339 | 最初 Linux 云部署验收基线，记录优化前测试与压测结果。保留用于前后比较，不应覆盖成优化后结论。 |
| [source-modes.json](data/source-modes.json) | 448 | 来源模式标签与证据：PUBLIC 标记为排位的用户确认，以及 ALGS 比赛分类；供入库和来源分类测试使用。 |
| [web-validation.json](data/web-validation.json) | 5597 | 本地网页流程验收记录：真实截图识别、预测、视口 / 交互和截图证据，不能当作公网 HTTPS 验收。 |

### data/cache

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [paired-probe.json](data/cache/paired-probe.json) | 888 | 最初同轮已知圈和揭晓响应的配对探测材料，包含采集时间与来源模式。 |
| [ringguessr-game.js](data/cache/ringguessr-game.js) | 7970 | 源站游戏前端 JavaScript 的研究副本，用于了解接口请求流程；不是本项目 web/app.js，不参与当前网页运行。 |
| [ringguessr-probe.json](data/cache/ringguessr-probe.json) | 286 | 最初接口探测保留的一份已知圈响应，用于理解 map 与 rings 字段。 |

### data/evaluation

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [EVALUATION_REPORT.md](data/evaluation/EVALUATION_REPORT.md) | 8260 | 历史检索独立评估的中文报告，方便理解指标、基线、来源敏感性和限制。 |
| [label-audit.json](data/evaluation/label-audit.json) | 12633 | 源站最终圈标签审计：目标半径分布、特殊样本、冲突原始行证据和分层评估政策；内部目标圈次仍未核实。 |
| [manifest.json](data/evaluation/manifest.json) | 248267 | 历史检索评估的冻结分区清单：数据哈希、随机种子、源对局别名分组、库 / 验证 / 测试划分及排除样本。 |
| [results.json](data/evaluation/results.json) | 3893092 | 历史检索评估的机器可读指标，按场景和已知圈数记录候选覆盖、圆心误差、基线与样本量探测。 |

### data/raw

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [collection-background-037af54677c840efb60c8884b8c2582f.error.log](data/raw/collection-background-037af54677c840efb60c8884b8c2582f.error.log) | 0 | 后台采集器的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-037af54677c840efb60c8884b8c2582f.log](data/raw/collection-background-037af54677c840efb60c8884b8c2582f.log) | 5385 | 后台采集器的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-2a468cc7600f4734bc6a1a2b48cc9dc2.error.log](data/raw/collection-background-2a468cc7600f4734bc6a1a2b48cc9dc2.error.log) | 1054 | 后台采集器的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-2a468cc7600f4734bc6a1a2b48cc9dc2.log](data/raw/collection-background-2a468cc7600f4734bc6a1a2b48cc9dc2.log) | 16550 | 后台采集器的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-68e028922e794831ad1fed6d8a7e5762-watch.error.log](data/raw/collection-background-68e028922e794831ad1fed6d8a7e5762-watch.error.log) | 0 | 采集监控的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-68e028922e794831ad1fed6d8a7e5762-watch.log](data/raw/collection-background-68e028922e794831ad1fed6d8a7e5762-watch.log) | 0 | 采集监控的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-68e028922e794831ad1fed6d8a7e5762.error.log](data/raw/collection-background-68e028922e794831ad1fed6d8a7e5762.error.log) | 0 | 后台采集器的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-68e028922e794831ad1fed6d8a7e5762.log](data/raw/collection-background-68e028922e794831ad1fed6d8a7e5762.log) | 88654 | 后台采集器的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-69f292e6ba7443028330f6222b21b117-watch.error.log](data/raw/collection-background-69f292e6ba7443028330f6222b21b117-watch.error.log) | 0 | 采集监控的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-69f292e6ba7443028330f6222b21b117-watch.log](data/raw/collection-background-69f292e6ba7443028330f6222b21b117-watch.log) | 0 | 采集监控的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-69f292e6ba7443028330f6222b21b117.error.log](data/raw/collection-background-69f292e6ba7443028330f6222b21b117.error.log) | 0 | 后台采集器的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-69f292e6ba7443028330f6222b21b117.log](data/raw/collection-background-69f292e6ba7443028330f6222b21b117.log) | 61538 | 后台采集器的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-81f8649cf8634aa4858f99235a5ddbf6-watch.error.log](data/raw/collection-background-81f8649cf8634aa4858f99235a5ddbf6-watch.error.log) | 0 | 采集监控的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-81f8649cf8634aa4858f99235a5ddbf6-watch.log](data/raw/collection-background-81f8649cf8634aa4858f99235a5ddbf6-watch.log) | 0 | 采集监控的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-81f8649cf8634aa4858f99235a5ddbf6.error.log](data/raw/collection-background-81f8649cf8634aa4858f99235a5ddbf6.error.log) | 0 | 后台采集器的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-81f8649cf8634aa4858f99235a5ddbf6.log](data/raw/collection-background-81f8649cf8634aa4858f99235a5ddbf6.log) | 86708 | 后台采集器的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-9e12a2b353594d0b8c4cbc29d7bd2bac.error.log](data/raw/collection-background-9e12a2b353594d0b8c4cbc29d7bd2bac.error.log) | 0 | 后台采集器的错误输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-background-9e12a2b353594d0b8c4cbc29d7bd2bac.log](data/raw/collection-background-9e12a2b353594d0b8c4cbc29d7bd2bac.log) | 88685 | 后台采集器的标准输出日志；文件名中的随机批次标识区分启动记录。是历史材料，存在不代表进程还在运行。 |
| [collection-watch.error.log](data/raw/collection-watch.error.log) | 0 | 采集监控的错误输出日志；文件即使存在也可能为空。 |
| [collection-watch.log](data/raw/collection-watch.log) | 0 | 采集监控的标准输出日志，保留运行过程和结束信息。 |
| [community-3000-3600.zip](data/raw/community-3000-3600.zip) | 98059742 | 此前下载研究的风暴点社区图片包，ZIP 内 581 个条目；地图不符合当前世界尽头训练范围，未作为本项目训练库。 |
| [ringguessr-pairs.jsonl](data/raw/ringguessr-pairs.jsonl) | 887297 | 采集原始配对响应，一行一轮，含重复和后续被隔离的响应。用于重新导入、对局追溯和标签核查，是正式库的原始依据。 |

### data/raw/checkpoints

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [handoff-20261012-010648.zip](data/raw/checkpoints/handoff-20261012-010648.zip) | 116691 | 2026-10-12 较早交接检查点，包含 25 个文档、代码和采集材料条目；用于恢复那一时刻的状态。 |
| [target-1000-complete-20261012-180452.zip](data/raw/checkpoints/target-1000-complete-20261012-180452.zip) | 285694 | 达到总量目标后的完成归档，含 28 个条目；与 completion-backup.json 配套校验。 |

### data/raw/collection-batches

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [7c7d389e640c4ef2a9a85ee331b44194-target-reached-progress.json](data/raw/collection-batches/7c7d389e640c4ef2a9a85ee331b44194-target-reached-progress.json) | 687 | 采集器批次进度归档，达到样本目标时保存；随机前缀为批次 ID，保留供故障追溯。 |
| [7c7d389e640c4ef2a9a85ee331b44194-target-reached-watch.json](data/raw/collection-batches/7c7d389e640c4ef2a9a85ee331b44194-target-reached-watch.json) | 430 | 采集监控状态归档，达到样本目标时保存；随机前缀为批次 ID，保留供故障追溯。 |
| [80a1fab326cd4d078ecc46c5bc422c50-collection-progress-before-user-stop.json](data/raw/collection-batches/80a1fab326cd4d078ecc46c5bc422c50-collection-progress-before-user-stop.json) | 1180 | 采集器批次进度归档，用户要求停止前的状态；随机前缀为批次 ID，保留供故障追溯。 |
| [80a1fab326cd4d078ecc46c5bc422c50-collection-watch-before-user-stop.json](data/raw/collection-batches/80a1fab326cd4d078ecc46c5bc422c50-collection-watch-before-user-stop.json) | 278 | 采集监控状态归档，用户要求停止前的状态；随机前缀为批次 ID，保留供故障追溯。 |
| [80a1fab326cd4d078ecc46c5bc422c50-paused-20261012-041927.json](data/raw/collection-batches/80a1fab326cd4d078ecc46c5bc422c50-paused-20261012-041927.json) | 1300 | 采集器批次进度归档，采集暂停时保存；随机前缀为批次 ID，保留供故障追溯。 |
| [80a1fab326cd4d078ecc46c5bc422c50-watch-paused-20261012-041927.json](data/raw/collection-batches/80a1fab326cd4d078ecc46c5bc422c50-watch-paused-20261012-041927.json) | 432 | 采集监控状态归档，采集暂停时保存；随机前缀为批次 ID，保留供故障追溯。 |
| [d2626c737ef54a7395f6064180085d52-watch-write-error-20261012-063649.json](data/raw/collection-batches/d2626c737ef54a7395f6064180085d52-watch-write-error-20261012-063649.json) | 379 | 采集监控状态归档，Windows 文件写入被占用 / 拒绝时保存；随机前缀为批次 ID，保留供故障追溯。 |
| [d2626c737ef54a7395f6064180085d52-write-error-20261012-063649.json](data/raw/collection-batches/d2626c737ef54a7395f6064180085d52-write-error-20261012-063649.json) | 1131 | 采集器批次进度归档，Windows 文件写入被占用 / 拒绝时保存；随机前缀为批次 ID，保留供故障追溯。 |
| [edfcf3de0f304385a09bde6c7f230eb5-progress.json](data/raw/collection-batches/edfcf3de0f304385a09bde6c7f230eb5-progress.json) | 701 | 采集器批次进度归档，早期批次的运行 / 结束状态；随机前缀为批次 ID，保留供故障追溯。 |
| [edfcf3de0f304385a09bde6c7f230eb5-watch.json](data/raw/collection-batches/edfcf3de0f304385a09bde6c7f230eb5-watch.json) | 392 | 采集监控状态归档，早期批次的运行 / 结束状态；随机前缀为批次 ID，保留供故障追溯。 |

### data/training

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [example-query.json](data/training/example-query.json) | 377 | 只含已知圈与适用范围的示例预测请求，没有真实目标答案；网页历史示例及压测使用它。 |
| [manifest.json](data/training/manifest.json) | 37528 | 运行必需的模型清单：正式库 / 分区 SHA-256、训练 / 验证 / 保留测试 ID、依赖版本、特征格式、适用范围、三个模型路径及哈希。加载器靠它检测材料不一致。 |
| [results.json](data/training/results.json) | 1153431 | 监督模型训练和验证的机器可读完整结果，包括各阶段胜出配置、误差、覆盖和基线。概率参考使用实际验证样本，不从这个文件直接套一个固定概率。 |
| [stage-1-selection.json](data/training/stage-1-selection.json) | 2195919 | 首圈输入模型的训练内部五折交叉验证及选型记录；证明配置选择依据，不是实时推理结果。 |
| [stage-2-selection.json](data/training/stage-2-selection.json) | 2191406 | 前两圈输入模型的五折选型详情。 |
| [stage-3-selection.json](data/training/stage-3-selection.json) | 2186338 | 前三圈输入模型的五折选型详情。 |
| [TRAINING_REPORT.md](data/training/TRAINING_REPORT.md) | 6169 | 训练方法、样本分区、候选模型、选型结果与验证指标的可读报告。 |

### deploy

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [Caddyfile.example](deploy/Caddyfile.example) | 595 | Caddy HTTPS 反向代理配置示例：把正式域名请求代理到本机 API，限制请求体并给出 JSON 错误。仍含示例域名，未安装 / 启用 / 验收正式 HTTPS。 |
| [compose.internal.yaml](deploy/compose.internal.yaml) | 819 | 目前服务器内部运行配置：无需域名，绑定 127.0.0.1:8765，不信任转发头，运行并发优化镜像；保留资源限制、健康检查依赖与重启策略。 |
| [compose.yaml](deploy/compose.yaml) | 934 | 未来正式 HTTPS 模式：需要明确 RINGLAB_PUBLIC_ORIGIN，信任本机代理，API 仍监听 loopback；容器只读、1 GiB / 2 CPU、有界队列、自动重启与滚动日志。当前尚未切换到此模式。 |

### models

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [stage-1.joblib](models/stage-1.joblib) | 2503614 | 已知首圈时使用的 ExtraTrees 回归模型，包含训练好的估计器、特征与适用范围；不会预测“第 1 圈”，而是从第 1 圈推测目标圈。 |
| [stage-2.joblib](models/stage-2.joblib) | 3170618 | 已知第 1、2 圈时使用的 ExtraTrees 回归模型，用更多已知信息预测目标圈位置。 |
| [stage-3.joblib](models/stage-3.joblib) | 3176205 | 已知第 1、2、3 圈时使用的 ExtraTrees 回归模型；运行时由 Workbench 加载并根据输入数选择。 |

### outputs

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [project-file-inventory.csv](outputs/project-file-inventory.csv) |  | 同一份完整清单的 CSV 版本，可用文本编辑器或表格软件阅读；UTF-8 BOM，含路径、类型、大小、分类、用途与说明依据。 |
| [project-file-inventory.html](outputs/project-file-inventory.html) |  | 本次完整文件 / 目录清单，可以按路径、用途和分类搜索，含第三方依赖与缓存。完全本地、无外部脚本或数据上传。 |

### outputs/backups

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [before-concurrency-20261013.zip](outputs/backups/before-concurrency-20261013.zip) | 47515 | 本轮并发优化前的源码备份，保留原识图匹配与容量设置。 |
| [before-fastapi-20261013.zip](outputs/backups/before-fastapi-20261013.zip) | 107787 | 迁移 FastAPI 服务前的源码备份，供核查和回退。 |

### outputs/qa

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [build-file-guide.py](outputs/qa/build-file-guide.py) | 54168 | 本次说明生成器：只遍历本地目录和读取源码结构，生成文件说明 / 完整 HTML 与 CSV 清单；不启动采集、训练、服务或远程连接。；主要接口：env_relative、package_info、kind_description、describe、project_file、code_symbols、make_rows、markdown、main |
| [concurrency-overload.py](outputs/qa/concurrency-overload.py) | 2105 | 云端五同时识图的过载验证脚本，检查四个任务接受 / 第五个 503、预测和健康可用以及结束后队列归零。；主要接口：send、recognize |
| [concurrency-server-state.json](outputs/qa/concurrency-server-state.json) | 846 | 并发版本部署后的服务器状态快照，供验收与回溯。 |
| [concurrency-update.zip](outputs/qa/concurrency-update.zip) | 12432 | 并发改造的小型更新归档，包含当时新增 / 修改源码、容量设置与验收材料；完整运行交付包在 releases。 |
| [continue-match.png](outputs/qa/continue-match.png) | 106210 | 继续上传同局截图、合并圈位流程的网页验收截图。 |
| [Dockerfile.qa-complete](outputs/qa/Dockerfile.qa-complete) | 89 | 最初完整 Linux QA 镜像补充步骤，加入来源模式分类文件，让相关采集测试能在独立 QA 镜像中执行。 |
| [fastapi-preview.stderr.log](outputs/qa/fastapi-preview.stderr.log) | 340 | FastAPI 本地预览进程的错误输出日志。 |
| [fastapi-preview.stdout.log](outputs/qa/fastapi-preview.stdout.log) | 30 | FastAPI 本地预览进程的标准输出日志。 |
| [fastapi-server.log](outputs/qa/fastapi-server.log) | 1943 | validate-deployment.py 启动临时 FastAPI 服务时保存的输出和错误日志。 |
| [geometry-fixture.png](outputs/qa/geometry-fixture.png) | 20955 | 几何与前端流程调试用测试图；生成素材不作为真实截图效果证据。 |
| [linux-qa.zip](outputs/qa/linux-qa.zip) | 1815306 | 服务器 QA 专用代码、测试与截图材料归档；测试材料与网页运行镜像分开。 |
| [linux-wheel-hashes.json](outputs/qa/linux-wheel-hashes.json) | 3217 | 每个 Linux wheel 与官方 PyPI 发行哈希的核验记录。 |
| [linux-wheelhouse.sha256](outputs/qa/linux-wheelhouse.sha256) | 88 | Linux wheel 归档的哈希，确认上传前后相同。 |
| [linux-wheelhouse.tar](outputs/qa/linux-wheelhouse.tar) | 134144000 | Linux 离线依赖 wheel 与校验表的集合归档，上传服务器用于离线构建。 |
| [orange-mask.png](outputs/qa/orange-mask.png) | 23152 | 识别调试用的橙色区域 / 遮罩诊断图，不是模型数据。 |
| [profile-vision.py](outputs/qa/profile-vision.py) | 1879 | 识图性能剖析脚本：计时 ORB / SIFT、匹配、Hough、变换和编码，比较线程设置，输出匹配质量与圈位。；主要接口：timed、TimedObject |
| [remote-build-mirrors.sh](outputs/qa/remote-build-mirrors.sh) | 230 | 一次性云部署 / 验收脚本：使用阿里云 Debian / PyPI 镜像源尝试构建；属于网络受限时的历史过程。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-build-offline.sh](outputs/qa/remote-build-offline.sh) | 1655 | 一次性云部署 / 验收脚本：解开并校验 Linux wheel，用临时 loopback wheel 服务离线构建运行 / QA 镜像，执行测试与 pip check，退出时停止临时服务。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-build.sh](outputs/qa/remote-build.sh) | 384 | 一次性云部署 / 验收脚本：导入离线 Python 基础镜像，再尝试普通 Docker 构建。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-concurrency-benchmark.sh](outputs/qa/remote-concurrency-benchmark.sh) | 1529 | 一次性云部署 / 验收脚本：停止旧内部服务、在临时候选容器执行两人 / 四人压测，再清理候选任务；不与两个模型进程长期同时运行。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-concurrency-qa.sh](outputs/qa/remote-concurrency-qa.sh) | 753 | 一次性云部署 / 验收脚本：解开并发更新包，构建运行与 QA 镜像，临时停止旧服务以控制内存，验证 Linux 测试和依赖。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-concurrency-release-check.sh](outputs/qa/remote-concurrency-release-check.sh) | 834 | 一次性云部署 / 验收脚本：补齐并发版本完整发布包，校验每个文件 SHA-256、Compose 配置与最终健康状态。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-concurrency-rollout.sh](outputs/qa/remote-concurrency-rollout.sh) | 1195 | 一次性云部署 / 验收脚本：校验新目录配置并把同一个内部 Compose 项目切换到并发镜像，等待 ready / healthy 并核查资源。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-concurrency-smoke.sh](outputs/qa/remote-concurrency-smoke.sh) | 2320 | 一次性云部署 / 验收脚本：新版本静态页面、模块、预测、来源 / 私有资源拒绝以及容器重启恢复检查。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-download-check.sh](outputs/qa/remote-download-check.sh) | 377 | 一次性云部署 / 验收脚本：测镜像源部分文件下载速度并查看当时容器资源，用于判断慢下载。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-final-state.sh](outputs/qa/remote-final-state.sh) | 1771 | 一次性云部署 / 验收脚本：记录最初部署最终状态：健康、监听、资源、重启策略与临时任务清理情况。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-inspect.sh](outputs/qa/remote-inspect.sh) | 297 | 一次性云部署 / 验收脚本：查看 Docker 版本、镜像与初始部署状态。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-load-test.sh](outputs/qa/remote-load-test.sh) | 815 | 一次性云部署 / 验收脚本：让 QA 容器对内部服务执行有限负载测试，并监测目标进程树资源。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-network-check.sh](outputs/qa/remote-network-check.sh) | 187 | 一次性云部署 / 验收脚本：检查当前容器及镜像源连通性，诊断构建下载失败。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-overload-check.sh](outputs/qa/remote-overload-check.sh) | 287 | 一次性云部署 / 验收脚本：执行旧队列容量版本的识图突发 / 503 和恢复检查。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-prepare-qa-data.sh](outputs/qa/remote-prepare-qa-data.sh) | 47 | 一次性云部署 / 验收脚本：准备独立 QA 所需数据与输入素材，使验收不依赖将测试截图装入运行镜像。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-profile-optimized.sh](outputs/qa/remote-profile-optimized.sh) | 379 | 一次性云部署 / 验收脚本：运行优化后识图耗时剖析，与旧方案对照。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-profile.sh](outputs/qa/remote-profile.sh) | 221 | 一次性云部署 / 验收脚本：运行优化前识图耗时剖析，定位 SIFT 全量匹配瓶颈。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-qa-complete.sh](outputs/qa/remote-qa-complete.sh) | 306 | 一次性云部署 / 验收脚本：补齐来源分类材料后的完整 Linux QA，修复早期 QA 镜像缺少测试输入的问题。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-qa.sh](outputs/qa/remote-qa.sh) | 380 | 一次性云部署 / 验收脚本：解开 Linux QA 资料，建立 QA 镜像，执行测试与依赖一致性检查。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-release-check.sh](outputs/qa/remote-release-check.sh) | 286 | 一次性云部署 / 验收脚本：最初 Linux 完整发布包的解包 / 指纹及内部服务检查。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-smoke-restart.sh](outputs/qa/remote-smoke-restart.sh) | 2270 | 一次性云部署 / 验收脚本：最初版本静态 / API / 拒绝路径检查与容器重启恢复验证。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-start-internal.sh](outputs/qa/remote-start-internal.sh) | 566 | 一次性云部署 / 验收脚本：校验并启动最初内部 Compose，检查 ready、容器状态和 loopback 监听。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [remote-stop-build.sh](outputs/qa/remote-stop-build.sh) | 117 | 一次性云部署 / 验收脚本：核对并停止当时卡住的构建容器；包含历史固定容器 ID，不是通用维护命令。 保留作为过程材料，执行前需核对其中的历史路径和目标。 |
| [requirements-linux.txt](outputs/qa/requirements-linux.txt) | 607 | 制作 Linux wheel 集合用的固定依赖清单，排除 Windows 专用项并加入验收所需包。 |
| [second-ring-only.png](outputs/qa/second-ring-only.png) | 1417093 | 连续上传流程使用的只含二圈的生成测试图，检查保留旧圈与添加新圈。 |
| [server-state.json](outputs/qa/server-state.json) | 846 | 最初部署检查时记录的服务器服务状态，属于当时快照。 |
| [ssh-deploy-connection.json](outputs/qa/ssh-deploy-connection.json) | 466 | SSH 部署连接参数与本机密钥 / known_hosts 路径记录；不是私钥本体，不在发布包中。本说明不展开连接参数内容。 |
| [third-ring-only.png](outputs/qa/third-ring-only.png) | 1418150 | 连续上传流程使用的只含三圈的生成测试图。 |
| [user-aligned-before.png](outputs/qa/user-aligned-before.png) | 1176105 | 旧识图方案的对齐诊断图，保留作前后比较。 |
| [user-aligned-sift.png](outputs/qa/user-aligned-sift.png) | 1176243 | SIFT 方案对齐后的诊断图，检查地图配准和圈位。 |
| [user-predictions.png](outputs/qa/user-predictions.png) | 99878 | 真实截图圈位确认后显示候选圈和估计概率的网页验收截图。 |
| [user-recognition.png](outputs/qa/user-recognition.png) | 57293 | 真实截图上传后自动定位和识圈界面的验收截图。 |
| [web-server.stderr.log](outputs/qa/web-server.stderr.log) | 6157 | 较早本地网页服务的错误输出日志。 |
| [web-server.stdout.log](outputs/qa/web-server.stdout.log) | 30 | 较早本地网页服务的标准输出日志。 |

### outputs/qa/linux-wheels

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [annotated_doc-0.0.5-py3-none-any.whl](outputs/qa/linux-wheels/annotated_doc-0.0.5-py3-none-any.whl) | 5302 | annotated_doc 的固定版本 wheel 安装包：类型 / 文档注解辅助；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [annotated_types-0.8.0-py3-none-any.whl](outputs/qa/linux-wheels/annotated_types-0.8.0-py3-none-any.whl) | 13427 | annotated_types 的固定版本 wheel 安装包：Python 类型约束注解；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [anyio-4.15.1-py3-none-any.whl](outputs/qa/linux-wheels/anyio-4.15.1-py3-none-any.whl) | 132079 | anyio 的固定版本 wheel 安装包：异步任务与线程协调，供 Web 依赖使用；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [certifi-2026.5.20-py3-none-any.whl](outputs/qa/linux-wheels/certifi-2026.5.20-py3-none-any.whl) | 134134 | certifi 的固定版本 wheel 安装包：HTTP 客户端使用的公共 CA 证书集合；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [click-8.5.0-py3-none-any.whl](outputs/qa/linux-wheels/click-8.5.0-py3-none-any.whl) | 125251 | click 的固定版本 wheel 安装包：命令行参数和命令组织，供依赖使用；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [cloudpickle-3.1.2-py3-none-any.whl](outputs/qa/linux-wheels/cloudpickle-3.1.2-py3-none-any.whl) | 22228 | cloudpickle 的固定版本 wheel 安装包：Python 对象序列化辅助；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [fastapi-0.143.0-py3-none-any.whl](outputs/qa/linux-wheels/fastapi-0.143.0-py3-none-any.whl) | 144665 | fastapi 的固定版本 wheel 安装包：后端 Web API 框架；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [h11-0.16.0-py3-none-any.whl](outputs/qa/linux-wheels/h11-0.16.0-py3-none-any.whl) | 37515 | h11 的固定版本 wheel 安装包：HTTP/1.1 协议处理；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [httpcore-1.0.9-py3-none-any.whl](outputs/qa/linux-wheels/httpcore-1.0.9-py3-none-any.whl) | 78784 | httpcore 的固定版本 wheel 安装包：HTTP 客户端底层连接和协议；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [httpx-0.28.1-py3-none-any.whl](outputs/qa/linux-wheels/httpx-0.28.1-py3-none-any.whl) | 73517 | httpx 的固定版本 wheel 安装包：HTTP 客户端，供接口测试与 QA 使用；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [idna-3.18-py3-none-any.whl](outputs/qa/linux-wheels/idna-3.18-py3-none-any.whl) | 65455 | idna 的固定版本 wheel 安装包：国际化域名编码；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [joblib-1.6.0-py3-none-any.whl](outputs/qa/linux-wheels/joblib-1.6.0-py3-none-any.whl) | 306115 | joblib 的固定版本 wheel 安装包：模型序列化保存 / 加载与并行工具；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [narwhals-2.27.1-py3-none-any.whl](outputs/qa/linux-wheels/narwhals-2.27.1-py3-none-any.whl) | 483211 | narwhals 的固定版本 wheel 安装包：数据结构兼容辅助，为依赖链提供支持；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [numpy-2.4.6-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl](outputs/qa/linux-wheels/numpy-2.4.6-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl) | 16633220 | numpy 的固定版本 wheel 安装包：数组、矩阵与数值计算；精确 SIFT 距离和模型输入会使用；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [opencv_python_headless-5.0.0.93-cp37-abi3-manylinux_2_28_x86_64.whl](outputs/qa/linux-wheels/opencv_python_headless-5.0.0.93-cp37-abi3-manylinux_2_28_x86_64.whl) | 61204038 | opencv_python_headless 的固定版本 wheel 安装包：不带图形桌面组件的 OpenCV 视觉库；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [opentelemetry_api-1.45.1-py3-none-any.whl](outputs/qa/linux-wheels/opentelemetry_api-1.45.1-py3-none-any.whl) | 60256 | opentelemetry_api 的固定版本 wheel 安装包：依赖链的遥测 API 接口；安装存在本身不证明启用了数据导出；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [pillow-12.2.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl](outputs/qa/linux-wheels/pillow-12.2.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl) | 7082423 | pillow 的固定版本 wheel 安装包：Pillow 图片读写、格式和像素检查；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [psutil-7.2.2-cp36-abi3-manylinux2010_x86_64.manylinux_2_12_x86_64.manylinux_2_28_x86_64.whl](outputs/qa/linux-wheels/psutil-7.2.2-cp36-abi3-manylinux2010_x86_64.manylinux_2_12_x86_64.manylinux_2_28_x86_64.whl) | 155560 | psutil 的固定版本 wheel 安装包：进程树 CPU / 内存等资源监测；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [pydantic-2.14.1-py3-none-any.whl](outputs/qa/linux-wheels/pydantic-2.14.1-py3-none-any.whl) | 488106 | pydantic 的固定版本 wheel 安装包：数据模型和输入校验；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [pydantic_core-2.50.1-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl](outputs/qa/linux-wheels/pydantic_core-2.50.1-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl) | 2158402 | pydantic_core 的固定版本 wheel 安装包：Pydantic 的本机高性能校验核心；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [scikit_learn-1.9.1-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl](outputs/qa/linux-wheels/scikit_learn-1.9.1-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl) | 9121732 | scikit_learn 的固定版本 wheel 安装包：机器学习库，包含 ExtraTrees 等估计器；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [scipy-1.18.1-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl](outputs/qa/linux-wheels/scipy-1.18.1-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl) | 35312578 | scipy 的固定版本 wheel 安装包：科学计算工具与机器学习依赖；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [starlette-1.7.0-py3-none-any.whl](outputs/qa/linux-wheels/starlette-1.7.0-py3-none-any.whl) | 78980 | starlette 的固定版本 wheel 安装包：FastAPI 使用的 ASGI / HTTP 基础功能；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [threadpoolctl-3.7.0-py3-none-any.whl](outputs/qa/linux-wheels/threadpoolctl-3.7.0-py3-none-any.whl) | 26362 | threadpoolctl 的固定版本 wheel 安装包：检查与控制底层数值库线程池；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [typing_extensions-4.16.0-py3-none-any.whl](outputs/qa/linux-wheels/typing_extensions-4.16.0-py3-none-any.whl) | 45571 | typing_extensions 的固定版本 wheel 安装包：较新的 Python 类型能力兼容；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [typing_inspection-0.4.4-py3-none-any.whl](outputs/qa/linux-wheels/typing_inspection-0.4.4-py3-none-any.whl) | 14750 | typing_inspection 的固定版本 wheel 安装包：类型注解检查辅助；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |
| [uvicorn-0.54.0-py3-none-any.whl](outputs/qa/linux-wheels/uvicorn-0.54.0-py3-none-any.whl) | 87427 | uvicorn 的固定版本 wheel 安装包：运行 ASGI 应用的 HTTP 服务进程；完整文件名给出 Python / ABI / 平台，供目标 Linux 离线安装。 |

### outputs/qa/python-base-blobs

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [068fedd6b0f109b8186d00d49327b6fc6747c428fd3c9a8739424ff5f38d7531](outputs/qa/python-base-blobs/068fedd6b0f109b8186d00d49327b6fc6747c428fd3c9a8739424ff5f38d7531) | 28233543 | 官方镜像压缩层 blob，文件名为内容 SHA-256。 |
| [068fedd6b0f109b8186d00d49327b6fc6747c428fd3c9a8739424ff5f38d7531.tar](outputs/qa/python-base-blobs/068fedd6b0f109b8186d00d49327b6fc6747c428fd3c9a8739424ff5f38d7531.tar) | 77895680 | 镜像层解压后的 tar，用于生成 docker load 归档。 |
| [2e6b5bbf5b2f372ef9b208e7c7c300675be97a6dc1bbe7e3ac0b9c20035fd70e](outputs/qa/python-base-blobs/2e6b5bbf5b2f372ef9b208e7c7c300675be97a6dc1bbe7e3ac0b9c20035fd70e) | 5527 | 镜像配置 JSON blob。 |
| [36d1aa696f899174752f594312e62a77a068b3f1a7a751bffafecdff61b55dcb](outputs/qa/python-base-blobs/36d1aa696f899174752f594312e62a77a068b3f1a7a751bffafecdff61b55dcb) | 250 | 官方镜像压缩层 blob，文件名为内容 SHA-256。 |
| [36d1aa696f899174752f594312e62a77a068b3f1a7a751bffafecdff61b55dcb.tar](outputs/qa/python-base-blobs/36d1aa696f899174752f594312e62a77a068b3f1a7a751bffafecdff61b55dcb.tar) | 5120 | 镜像层解压后的 tar，用于生成 docker load 归档。 |
| [59dae010ffdc12f24a794eec2ca47e675613b78a165c26b389ea7f670919f998](outputs/qa/python-base-blobs/59dae010ffdc12f24a794eec2ca47e675613b78a165c26b389ea7f670919f998) | 12506022 | 官方镜像压缩层 blob，文件名为内容 SHA-256。 |
| [59dae010ffdc12f24a794eec2ca47e675613b78a165c26b389ea7f670919f998.tar](outputs/qa/python-base-blobs/59dae010ffdc12f24a794eec2ca47e675613b78a165c26b389ea7f670919f998.tar) | 37857280 | 镜像层解压后的 tar，用于生成 docker load 归档。 |
| [6f59d65eb126bdbbfafbdc6551ec22d189bcf11e4c4f556e1cb95f03dd424f5c](outputs/qa/python-base-blobs/6f59d65eb126bdbbfafbdc6551ec22d189bcf11e4c4f556e1cb95f03dd424f5c) | 3519874 | 官方镜像压缩层 blob，文件名为内容 SHA-256。 |
| [6f59d65eb126bdbbfafbdc6551ec22d189bcf11e4c4f556e1cb95f03dd424f5c.tar](outputs/qa/python-base-blobs/6f59d65eb126bdbbfafbdc6551ec22d189bcf11e4c4f556e1cb95f03dd424f5c.tar) | 9570304 | 镜像层解压后的 tar，用于生成 docker load 归档。 |

### outputs/releases

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [python-3.13.13-slim-bookworm-amd64.tar.gz](outputs/releases/python-3.13.13-slim-bookworm-amd64.tar.gz) | 44097029 | 官方 Linux amd64 Python 基础镜像离线归档，服务器 docker load 使用，解决 Docker Hub 拉取超时；不是项目代码发布包。 |
| [python-3.13.13-slim-bookworm-amd64.tar.gz.sha256](outputs/releases/python-3.13.13-slim-bookworm-amd64.tar.gz.sha256) | 109 | 上述基础镜像归档的 SHA-256，用于传输完整性校验。 |
| [python-3.13.13-slim-bookworm-amd64.tar.gz.source.json](outputs/releases/python-3.13.13-slim-bookworm-amd64.tar.gz.source.json) | 493 | 基础镜像来源与清单摘要记录，用于追溯官方镜像及平台。 |
| [ringlab-fastapi-20261013-concurrency.zip](outputs/releases/ringlab-fastapi-20261013-concurrency.zip) | 9623251 | 当前并发优化版本发布包，42 个运行文件及清单；服务器已核验并更新到对应版本。 |
| [ringlab-fastapi-20261013-linux.zip](outputs/releases/ringlab-fastapi-20261013-linux.zip) | 9621352 | Linux 部署准备更新包，41 个运行文件及清单，加入可选镜像源 / 离线材料支持和内部 Compose。 |
| [ringlab-fastapi.zip](outputs/releases/ringlab-fastapi.zip) | 9616498 | 最早的 FastAPI 运行发布包，39 个运行文件及发布清单；不是当前并发版本。 |

### ringlab

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [__init__.py](ringlab/__init__.py) | 59 | 标识 ringlab 为 Python 包，并给出包的简短说明；不是服务启动入口。 |
| [config.py](ringlab/config.py) | 2949 | 运行配置：读取并验证 RINGLAB_* 环境变量，包括监听地址、HTTPS Origin、可信代理、工作线程、队列、限流与超时；拒绝不合法配置。；主要接口：Settings |
| [data.py](ringlab/data.py) | 4698 | 数据基础设施：地图坐标范围、正式库路径、样本几何 / 字段校验、加载、去重检查、元信息和 JSON 原子写入。Windows 短暂文件占用时有限重试，保留旧文件。；主要接口：validate_record、load_records、save_records、write_json_atomic、metadata |
| [evaluate.py](ringlab/evaluate.py) | 23922 | 历史检索效果评估：按源对局和别名分组冻结分区，防止同局泄漏，计算圆心误差、候选覆盖和基线；核对目标标签，生成 evaluation 下的报告。；主要接口：source_ids、source_groups、make_split、assert_no_leakage、compatible_pool、center_error、percentile、error_summary、evaluate_queries、summarize、label_audit、render_report、main |
| [ingest.py](ringlab/ingest.py) | 5683 | 原始响应入库：把同轮已知圈与揭晓目标配对正规化，仅接收世界尽头和有效来源；合并重复、保留来源别名，异常响应单独隔离，并写导入报告。；主要接口：normalize、ingest、_is_json、main |
| [limits.py](ringlab/limits.py) | 2397 | 服务承载控制：按客户端限流、有界线程池和排队名额。上传前先占位，计算超时后仍保留任务占用直到真正完成，避免并发越积越多。；主要接口：BusyError、RateLimiter、BoundedPool |
| [matching.py](ringlab/matching.py) | 3110 | 并发优化使用的精确 SIFT 匹配：分块计算最近邻，只对初筛候选做反向核对，保留原有比率与双向匹配规则；非量化描述子回退 OpenCV 精确计算。；主要接口：quantized_sift、nearest、sift_matches |
| [model.py](ringlab/model.py) | 5605 | 模型推理与几何处理：把已知圈转为特征，预测相对圆心偏移，再投影到满足已知圈和地图边界的区域。按输入圈数选择模型，检查地图 / 来源 / build 范围；也提供命令行推理入口。；主要接口：features、target_offset、decode_offset、project_center、predict_centers、predict_one、main |
| [probability.py](ringlab/probability.py) | 4387 | 估计命中概率与候选合并：使用独立历史验证对局的归一化模型误差估计候选圆包含真实目标圆心的概率，提供区间；平移缩放历史候选、几何校正、近似去重后最多返回五项。不是当前实战校准概率。；主要接口：HistoricalProbability、shortlist |
| [report.py](ringlab/report.py) | 12555 | 生成数据说明：读取正式库、采集状态、冲突审计、评估和训练结果，写入 data/DATASET.md，输出汇总统计。生成时会写报告文件，旧报告文字可能滞后于新网页功能。；主要接口：main |
| [retrieval.py](ringlab/retrieval.py) | 4398 | 历史圈型检索：校验已知圈，从同地图版本样本中按加权圈位距离寻找相似对局、去重目标圈并给出相似程度；也审计重复首圈与目标冲突。；主要接口：validate_observations、distance、retrieve、audit |
| [server.py](ringlab/server.py) | 11097 | FastAPI / Uvicorn 服务入口。提供健康、元信息、预测、识图四个 API 和受限静态文件访问；管理启动初始化、请求体大小、超时、来源校验、安全响应头、任务队列和隐私日志。；主要接口：error、ResponsePolicy、reject_constant、read_json、create_app、main |
| [train.py](ringlab/train.py) | 19727 | 离线监督训练：核查固定分区与指纹，比较候选回归器，在训练内部五折分组选型，训练三个圈数模型并生成验证指标 / 清单。网页请求不会自动执行训练。；主要接口：candidate_configs、build_estimator、checked_partitions、prediction_rows、metrics、select_candidate、train_stage、render_report、main |
| [vision.py](ringlab/vision.py) | 9917 | 截图识别：核验 JPG / PNG、文件大小与像素数，先用 ORB、再用 SIFT 和 RANSAC 对齐地图，检测候选圆，支持手动框选区域，并返回对齐预览及圈位建议。需要用户确认圈次。；主要接口：decode_image、bounds_homography、ScreenshotRecognizer |
| [workbench.py](ringlab/workbench.py) | 6384 | 应用功能协调层。启动时核验依赖、正式库和模型指纹，加载三个模型、检索库、概率参考及识图器；预测时合并算法结果，识图时只在内存处理上传数据并用锁保护识图器。；主要接口：model_path、Workbench |

### scripts

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [collect-ringguessr.ps1](scripts/collect-ringguessr.ps1) | 12234 | Ring Guessr 访客流程采集器：按 PUBLIC / ALGS / BOTH 收集同轮已知圈和最终圈，保存原始 JSONL、同步正式库、记录进度并有限恢复临时错误。当前采集目标已达到，保持暂停。 |
| [fetch-base-image.py](scripts/fetch-base-image.py) | 6976 | 官方 Python Docker 基础镜像离线下载：不依赖本机 Docker，校验清单、blob 和解压层哈希，生成可 docker load 的归档；跨主机重定向不转发认证头。；主要接口：StripRedirectAuth、sha、fetch、blob、add_bytes、main |
| [freeze-runtime.py](scripts/freeze-runtime.py) | 956 | 依赖锁定维护脚本：从当前已安装包读取精确版本，重写 requirements.lock.txt。用于经过验证的版本更新，不是普通启动步骤。 |
| [load-test.py](scripts/load-test.py) | 6515 | 有限并发压测：调用健康、预测和真实截图识图，记录状态 / 耗时、进程树 CPU / RSS 及恢复情况；核验目标 PID，支持两人或四人场景。；主要接口：send、main |
| [pack-release.py](scripts/pack-release.py) | 2130 | 制作运行发布 ZIP：先核验应用材料，再按白名单装入源码、前端、模型、指定数据、部署文件与少数脚本，生成逐文件 SHA-256 manifest；不装入原始采集、测试截图、环境或 SSH 连接记录。；主要接口：main |
| [remote-deploy.py](scripts/remote-deploy.py) | 1944 | 已授权的 SSH / SCP 辅助工具：执行服务器 shell 脚本、上传和下载文件，使用已核对的主机公钥与专用部署密钥路径。连接记录不在发布包中，私钥在项目外。；主要接口：main |
| [start-web.ps1](scripts/start-web.ps1) | 400 | Windows 本地网页启动器：使用项目 .venv，切换到项目根目录后运行 python -m ringlab.server，可指定端口。 |
| [validate-deployment.py](scripts/validate-deployment.py) | 1815 | 本机部署验收包装器：启动自己的临时 Uvicorn 子进程，等待 ready，调用 load-test.py，最后关闭这个子进程，不处理其他未知服务。 |
| [watch-ringguessr-collection.ps1](scripts/watch-ringguessr-collection.ps1) | 4609 | 采集批次监控：跟踪指定采集器进程、刷新报告，只有正常批次耗尽预算且未达目标时才继续，使用互斥锁避免重复监控；故障 / 限制时停止。 |

### tests

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [test-collector-modes.ps1](tests/test-collector-modes.ps1) | 1010 | PowerShell 采集模式回归，检查 PUBLIC / ALGS / BOTH 参数不被拆成首字母；不会启动真实采集。 |
| [test-collector-recovery.ps1](tests/test-collector-recovery.ps1) | 8403 | PowerShell 采集恢复与暂停逻辑回归，以模拟网络和等待执行，不访问实际接口。 |
| [test-match-session.mjs](tests/test-match-session.mjs) | 1747 | 前端本局状态回归，检查新增圈、跳圈 / 重复 / 嵌套错误、新对局与保存数据恢复规则。 |
| [test-ui-math.mjs](tests/test-ui-math.mjs) | 666 | Node 可执行的前端几何回归，检查三点画圆和输入几何。 |
| [test_atomic_write.py](tests/test_atomic_write.py) | 2909 | Windows 原子写入：短暂锁重试、持续锁停止、其他权限错误不误重试，以及旧数据不被截断。；主要接口：AtomicWriteTests |
| [test_collection.py](tests/test_collection.py) | 5165 | 原始入库：仅首圈也可用、缺目标 / 其他地图 / 错来源拒绝、重复合并、来源别名、冲突保留与异常隔离。；主要接口：pair、CollectionTests |
| [test_evaluation.py](tests/test_evaluation.py) | 4997 | 独立对局评估：传递别名分组、分区稳定与防泄漏、来源 / 版本范围、去重覆盖及误差统计。；主要接口：record、EvaluationTests |
| [test_matching.py](tests/test_matching.py) | 2533 | 精确 SIFT 优化：分块与原 OpenCV 距离 / 双向匹配一致、重复与并列选择、非量化回退、空描述子。；主要接口：original_matches、MatchingTests |
| [test_model.py](tests/test_model.py) | 6044 | 模型特征与推理：不读取答案、相对偏移可还原、几何投影、范围核验、训练内部选型、分区校验及保存重载。；主要接口：ModelTests |
| [test_probability.py](tests/test_probability.py) | 1378 | 历史误差概率：平移 / 缩放一致、候选事件可重叠、参考样本缺失或分区重叠时拒绝。；主要接口：ProbabilityTests |
| [test_service_limits.py](tests/test_service_limits.py) | 13212 | 服务承载与配置：有界排队、第五识图拒绝、超时占位、健康 / 预测独立、限流表、请求体与慢上传、来源、隐私日志与跨平台模型路径。；主要接口：StubWorkbench、ServiceTests、StreamingTests、ConfigurationTests |
| [test_vision.py](tests/test_vision.py) | 4585 | 图像识别：真实原图与缩小 JPEG 两圈识别、文件真实格式 / 大小 / 像素限制、手动框选、空图失败与圈次不自动强定。；主要接口：image_bytes、VisionTests |
| [test_web.py](tests/test_web.py) | 5867 | 网页 HTTP 集成：静态页面与模块、私有资源不暴露、元信息、三种圈数预测、错误请求 / 图片反馈。；主要接口：WebTests |

### tests/fixtures

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [worlds-edge-user.png](tests/fixtures/worlds-edge-user.png) | 1800751 | 固定的真实用户游戏截图回归样本，检查自动对齐与暗圈识别；只供测试，不进入正式样本库或模型训练。 |

### web

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [app.js](web/app.js) | 26487 | 网页交互主程序：读取 API 元信息、上传与识图、圈次确认、手动三点画圆、地图缩放、调用预测、候选切换、图层显示、取消与超时反馈、本局状态保存和新对局清空。 |
| [geometry.mjs](web/geometry.mjs) | 1251 | 独立前端几何函数：检查圈位有效性，根据三个边界点拟合圆，供手动校正和单元测试使用。 |
| [index.html](web/index.html) | 8747 | 网页结构：圈位编辑、地图与图层、上传 / 框选 / 识别确认弹窗、预测结果和使用说明。由 app.js 驱动，style.css 提供样式。 |
| [session.mjs](web/session.mjs) | 2458 | 本局圈位状态规则：连续圈前缀、合并新圈、拒绝重复 / 跳圈 / 不嵌套输入，以及恢复保存数据。实际 sessionStorage 存取由 app.js 执行，不存上传截图。 |
| [style.css](web/style.css) | 14479 | 网页外观与适配：颜色、字体、排版、按钮、结果卡片、地图和弹窗，以及手机屏幕布局。 |

### web/assets

| 文件 | 字节数 | 用途 |
| --- | ---: | --- |
| [worlds-edge.jpg](web/assets/worlds-edge.jpg) | 567601 | 运行使用的压缩世界尽头底图：网页地图展示和后端截图配准都引用它，也是发布包 / 镜像包含的底图。 |
| [worlds-edge.png](web/assets/worlds-edge.png) | 24369402 | 4096×4096 世界尽头源底图，保留较完整的原始图像；当前网页与识图默认使用 JPG，PNG 不在运行发布白名单内。 |

## 两个 Python 环境的内部文件

`.venv` 是日常开发环境，但它的 `include-system-site-packages = true`，所以部分包实际来自系统 Python，不能把这里所有文件当成完整可复制的运行环境。`outputs/qa/clean-runtime` 的此项为 false，用来验证独立安装固定依赖。目标服务器运行 Docker 中的 Linux 环境，不直接使用这两套 Windows 环境。

| 文件 / 子目录 | 具体作用 |
| --- | --- |
| `pyvenv.cfg` | Python 来源、版本、是否读取系统级包等环境配置。 |
| `Scripts/python.exe` / `pythonw.exe` | 此环境的 Python 启动器；后者不显示控制台。 |
| `Scripts/pip*.exe` | 在这个环境里安装 / 查询 Python 包。 |
| `Scripts/activate*` / `Activate.ps1` | 为不同终端激活环境。 |
| `Scripts/deactivate.bat` | CMD 下撤销环境激活。 |
| `Scripts/uvicorn.exe` / `fastapi.exe` 等 | 已安装库对应的命令行启动器，不是另写的项目代码。 |
| `Lib/site-packages/` | 环境安装的第三方库与安装元数据。 |
| `Include/` | 扩展编译头文件的位置，本次环境可能为空。 |
| `*.dist-info/` | 每个 wheel 的版本、依赖、许可证、安装清单与入口元数据。 |
| `__init__.py` / `__main__.py` | Python 子包初始化 / 命令行入口。 |
| `*.py` / `*.pyi` | 依赖功能源码 / 类型声明。 |
| `*.pyd` / `*.dll` | Windows 编译扩展和动态库。 |
| `__pycache__/*.pyc` | 自动缓存，文件名带 Python 版本，不是手写源码。 |
| 依赖自带 `tests/` / `data/` | 依赖库自己的测试与资源，不是本项目训练对局。 |

### 主要依赖分别负责什么

| 包 / 导入名 | 作用 |
| --- | --- |
| `numpy` | 数组、矩阵与数值计算；精确 SIFT 距离和模型输入会使用 |
| `numpy.libs` | NumPy 所需的本机数学动态库 |
| `scipy` | 科学计算工具与机器学习依赖 |
| `scipy.libs` | SciPy 所需的本机数学动态库 |
| `sklearn` | scikit-learn 机器学习库，包含 ExtraTrees 等估计器 |
| `scikit-learn` | 机器学习库，包含 ExtraTrees 等估计器 |
| `scikit_learn` | 机器学习库，包含 ExtraTrees 等估计器 |
| `PIL` | Pillow 图片读写、格式和像素检查 |
| `pillow` | Pillow 图片读写、格式和像素检查 |
| `cv2` | OpenCV 视觉库，ORB / SIFT / RANSAC / 圆检测 |
| `opencv_python_headless` | 不带图形桌面组件的 OpenCV 视觉库 |
| `joblib` | 模型序列化保存 / 加载与并行工具 |
| `cloudpickle` | Python 对象序列化辅助 |
| `threadpoolctl` | 检查与控制底层数值库线程池 |
| `narwhals` | 数据结构兼容辅助，为依赖链提供支持 |
| `fastapi` | 后端 Web API 框架 |
| `uvicorn` | 运行 ASGI 应用的 HTTP 服务进程 |
| `starlette` | FastAPI 使用的 ASGI / HTTP 基础功能 |
| `pydantic` | 数据模型和输入校验 |
| `pydantic_core` | Pydantic 的本机高性能校验核心 |
| `annotated_types` | Python 类型约束注解 |
| `annotated_doc` | 类型 / 文档注解辅助 |
| `typing_extensions` | 较新的 Python 类型能力兼容 |
| `typing_inspection` | 类型注解检查辅助 |
| `anyio` | 异步任务与线程协调，供 Web 依赖使用 |
| `h11` | HTTP/1.1 协议处理 |
| `click` | 命令行参数和命令组织，供依赖使用 |
| `opentelemetry` | 依赖链的遥测 API 接口；安装存在本身不证明启用了数据导出 |
| `opentelemetry_api` | 依赖链的遥测 API 接口；安装存在本身不证明启用了数据导出 |
| `httpx` | HTTP 客户端，供接口测试与 QA 使用 |
| `httpcore` | HTTP 客户端底层连接和协议 |
| `certifi` | HTTP 客户端使用的公共 CA 证书集合 |
| `idna` | 国际化域名编码 |
| `psutil` | 进程树 CPU / 内存等资源监测 |
| `pip` | Python 包安装工具 |
| `colorama` | Windows 终端颜色兼容 |
| `tzdata` | 时区数据文件 |

## 本次核对的运行与材料关系

- 当前云运行版本是 `ringlab:20261013-concurrency`，内部服务监听服务器 `127.0.0.1:8765`；本次仅解释文件，没有重新连接或更新服务器。
- `codeqiqi.com` 已购买且用户确认实名通过；ICP / DNS / 正式 Origin / HTTPS 与公网验收尚待完成。配置示例存在不等于已上线。
- 正式库 1001 条，三个模型和固定训练清单互相有 SHA-256 校验；样本和训练材料是运行证据。
- 数据采集与定时任务仍暂停，日志 / 状态文件存在不表示后台采集仍运行。
- 网页上传只在内存处理；本地 fixture 与 outputs 图片是特意保存的回归 / 验收素材。
- `outputs/qa` 的一次性脚本保留历史版本路径与个别固定容器 ID；文件说明不是要求重新执行这些脚本。
- 日常阅读顺序建议：README → PROJECT_PLAN 顶部 → WEB_GUIDE → 本说明；修改页面看 web，修改识图看 vision / matching，修改预测看 model / retrieval / probability，维护云运行看 DEPLOYMENT / deploy。
