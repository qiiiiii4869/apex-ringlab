# 部署准备与回退

2026-10-13：已通过用户授权的 SSH 在阿里云杭州 ECS 完成内部部署。Ubuntu 22.04.5 / 2 vCPU / 2 GiB / 40 GiB，公网带宽峰值 5 Mbps、按流量计费；服务只监听服务器 `127.0.0.1:8765`，没有开放公网网页。用户已购买 `codeqiqi.com` 并确认域名实名认证通过；备案 / DNS / 正式 Origin / HTTPS 接入待进行。初期供自己和几位中国大陆的朋友试用，域名单独预算；公网流量费用不默认包含在服务器年费或学生券中。

备案准备：域名实名持有人须与备案主体一致；实际实名通过时间、备案主体 / 省份与提交结果尚未确认。阿里云建议实名完成至少三天后申请，避免管局尚未获取最新信息。同一账号购买服务器并备案时可直接选择 ECS，无需手动申请备案服务码；实际可备案资格以控制台核验为准。[阿里云备案流程 FAQ](https://help.aliyun.com/zh/icp-filing/basic-icp-service/support/for-the-record-process-faq)。已购买域名不等于 ICP 已审核通过，当前内部 Compose 继续运行；备案通过后再接入正式域名。

最新并发优化已更新服务器，Windows 和 Linux 各 65 项 Python 回归、pip check、静态文件 / JS MIME、1～3 圈预测、来源拒绝、私有文件拒绝、真实截图并发与容器重启恢复通过。优化后的两人识图最长约 5.91 秒（先前 26.54 秒）；四人同时识图 4/4 成功、最长约 10.90 秒。4 并发连续 8 次预测 / 识图均 8/8 成功。RSS 峰值约 758 MiB，容器仍限额 1 GiB / 2 CPU。5 个同时识图请求为 4 个成功 / 1 个 503，期间预测约 0.202 秒、健康检查约 0.046 秒，结束后 ready。报告见 `data/concurrency-validation.json`；`data/server-validation.json` 为优化前的部署基线。当前只覆盖所测截图和场景，真实 HTTPS 和目标环境浏览器交互仍待验收。

当前服务器项目目录为 `/opt/ringlab-concurrency-20261013`，镜像 `ringlab:20261013-concurrency`，目录 `.env` 已保存发行标签。旧目录 `/opt/ringlab-20261013`、旧镜像 `ringlab:20261013-fastapi` 保留供回退。域名前的内部服务由 `deploy/compose.internal.yaml` 管理，配置只监听 loopback、不信任转发头，非 root / 只读文件系统 / 自动重启 / 日志滚动均已生效：

```bash
cd /opt/ringlab-concurrency-20261013
docker compose -p ringlab-internal -f deploy/compose.internal.yaml ps
curl --fail http://127.0.0.1:8765/api/health
```

取得已备案域名后，先停止内部 Compose 项目，再使用配置了正式 HTTPS Origin 的 `deploy/compose.yaml`，避免两个项目抢占 8765 端口。内部模式仅用于准备和测试，其本地模式图片说明不能作为公网运行的最终说明。

## 本地启动

需要 CPython 3.13，推荐训练时使用的 3.13.13。固定依赖见 `requirements.lock.txt`；启动检查 NumPy / scikit-learn / joblib / SciPy / threadpoolctl 与训练清单的实际版本一致。不要仅升级 scikit-learn 再读取旧 joblib 模型。

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\scripts\start-web.ps1
```

原启动命令 `python -m ringlab.server --port 8765` 保留。健康检查为 `http://127.0.0.1:8765/api/health`。端口占用时改用 `--port 8766`，不停止未知进程。

## 配置

全部配置通过 `RINGLAB_` 环境变量读取；CLI 的 `--host` / `--port` 可覆盖监听地址和端口。

| 变量 | 默认 | 用途 |
| --- | --- | --- |
| `RINGLAB_HOST` / `RINGLAB_PORT` | `127.0.0.1` / `8765` | API 内部监听 |
| `RINGLAB_PUBLIC_ORIGIN` | 未设置 | 真实 `https://域名[:端口]`，不含路径或末尾斜线；设置后只接受该 Origin |
| `RINGLAB_TRUSTED_PROXIES` | `127.0.0.1` | 信任的反向代理 IP / 网段；不允许 `*`；空值表示不信任代理 |
| `RINGLAB_PREDICTION_WORKERS` / `RINGLAB_PREDICTION_QUEUE` | `1` / `7` | 预测线程数与额外等待名额，总容量 8 |
| `RINGLAB_RECOGNITION_QUEUE` | `3` | 识圈固定一个计算线程，额外三个等待名额，总容量 4 |
| `RINGLAB_UPLOAD_TIMEOUT` / `RINGLAB_TASK_TIMEOUT` | `20` / `45` 秒 | 请求体读取时间 / 排队及计算等待时间 |
| `RINGLAB_PREDICTION_RATE` / `RINGLAB_RECOGNITION_RATE` | `60` / `10` | 每个 IP 每分钟预测 / 识别上限；共享公网 IP 的朋友共用额度 |
| `RINGLAB_RATE_CLIENTS` | `4096` | 限流身份表上限；一分钟过期，不写磁盘 |
| `RINGLAB_CV_THREADS` | `2` | OpenCV 内部线程数 |
| `RINGLAB_CONNECTIONS` | `32` | Uvicorn 活跃连接 / 请求任务上限 |

来源校验接受无 Origin 的命令行 / 健康检查请求；不会根据客户端 Host / X-Forwarded-Host 自动放行新来源。Origin 是浏览器请求保护，不是访问密码。保留同域名 `/api/...` 相对路径，不启用跨域 CORS。

POST 的 JSON 总体限制为识图 12 MiB（含 base64），预测 64 KiB。实际图片仍限制 8 MiB、JPG/PNG、至少 256×256 和最多 2,000 万像素。流式请求即使未声明 Content-Length 也会限长。超载返回 503，频率超限 429，上传超时 408，计算等待超时 504；均保留前端本局圈位，支持重试。Uvicorn 或反向代理在更外层拒绝请求时可能返回非 JSON，前端也提供可读反馈。

线程计算无法安全强制中止。计算超时仅结束请求等待，占用名额直到实际计算完成；客户端取消也不提前释放名额，防止无限积累后台任务。如果 OpenCV 长时间卡住，应重启该服务容器；启动时重新校验模型。此阶段固定一个 Uvicorn 进程，不自行增加 workers；多进程会复制模型，并使限流 / 队列变成每个进程各自一份。

SIFT 匹配优化位于 `ringlab/matching.py`：对 128 维、0～255 整数量化的 float32 描述子，按每块 128 行计算精确 L2 最近邻；距离矩阵工作区只随块宽和底图特征数增长。保留原比率筛选、双向最近邻、RANSAC 和圈位核验；反向匹配只计算初筛候选。非量化描述子走原 OpenCV 精确距离路径。新增检查覆盖块边界、距离、重复 / 等距点和回退路径，原图及压缩 JPEG 回归通过。没有增加识图计算线程、复制模型或缓存上传图片。接口依据：[OpenCV BFMatcher](https://docs.opencv.org/4.x/d3/da1/classcv_1_1BFMatcher.html)。

## Linux 安装与容器

可先在 Linux 用同版本 Python 创建虚拟环境、安装固定依赖，执行 `python -m ringlab.server`。训练清单中的 Windows `models\\stage-N.joblib` 在加载时转换路径分隔符；训练清单和模型文件本身不改写。

`Dockerfile` 使用 CPython 3.13.13，非 root 用户运行，明确只复制服务代码、网页 JPG 底图、三个模型、正式库、训练清单及无答案示例。不包含原始采集响应、诊断图、用户截图和测试夹具；也没有提供模型或数据下载路径。

若大陆服务器无法连接 Docker Hub，可在能连接官方源的本机运行 `scripts/fetch-base-image.py`，将生成的基础镜像归档上传到服务器，核对旁附 SHA-256 后用 `docker load -i 文件.tar.gz` 导入。该脚本固定官方 Linux amd64 清单摘要，并校验镜像配置、下载 blob 和层 diff-id；实际 Docker 导入及构建仍需在目标环境验证。归档只含基础 Python 镜像，不含服务器账号或 SSH 私钥。

构建支持可选 `DEBIAN_MIRROR` 和 `PYPI_INDEX_URL` 参数，用于网络可达的软件镜像站；不更改固定 Python 依赖版本，不关闭 TLS 或 APT 签名校验。阿里云目标环境可采用：

```bash
docker build --memory 1g \
  --build-arg DEBIAN_MIRROR=https://mirrors.aliyun.com \
  --build-arg PYPI_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
  -t ringlab:20261013-fastapi .
```

本次实际构建还使用了预先从官方 PyPI 下载并校验的 Linux wheel。`PIP_NO_INDEX=1` 与 `PIP_FIND_LINKS` 可指定离线 wheel 来源；使用 `--network host` 从服务器 loopback 的临时软件包服务安装，完成后该临时服务已退出。包内哈希核验通过，不增加未固定版本依赖。离线包和 QA 材料留在服务器私有目录，运行镜像没有包含测试截图。

网络安装问题分别核查基础镜像、Debian 软件源和 Python 软件源，不通过升级模型依赖来绕过固定版本检查。参考：[Docker 离线导入](https://docs.docker.com/reference/cli/docker/image/load/)、[阿里云 Debian 镜像](https://developer.aliyun.com/mirror/debian/)、[阿里云 PyPI 镜像](https://developer.aliyun.com/mirror/pypi)。

`deploy/compose.yaml` 使用 **Linux host 网络**，服务仍只绑定 `127.0.0.1:8765`；同机反向代理可保持来源 IP 的信任链。它不是 Windows Docker Desktop 示例。默认 1 GiB 内存上限、2 CPU 上限、128 个 PID；最终机器应留出操作系统和代理内存，并在该机器重新压测。

```bash
export RINGLAB_PUBLIC_ORIGIN=https://your-filed-domain.example
export RINGLAB_RELEASE=20261013-fastapi
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml up -d
curl --fail http://127.0.0.1:8765/api/health
```

开发用 Windows 主机没有 Docker；目标 Ubuntu ECS 已完成镜像构建、启动、1 GiB / 2 CPU 限额检查及并发测试。公网配置及真实 HTTPS 仍待验收。

## HTTPS 代理

`deploy/Caddyfile.example` 给出 Caddy 反向代理配置，替换实际已备案域名后在服务器上校验配置；通过 Caddy 的正常 HTTPS 流程配置证书。只开放需要的 80 / 443 端口，API 8765 保持本机监听。若改为容器桥接代理，须明确修改监听 / 代理网络与可信代理 IP，不能照搬 loopback 配置。

代理总请求体限制 12 MB（大于合法 8 MiB 图片的 base64 JSON），响应等待 70 秒；应用另有上传和计算超时。代理访问日志默认关闭，避免记录访客 IP、URL 查询参数；服务日志只记录固定路由名、状态和耗时，异常仅记类型，不记图片正文、圈位、请求查询参数或完整异常文本。Docker 日志限额滚动。应用聚合计数在 `app.state.metrics`，不暴露包含访客信息的指标接口。页面通过 metadata 自动显示本机或 HTTPS 服务器的图片处理说明；图片仍仅内存处理，不保存、不进入训练库。

本机没有 Caddy，代理配置尚待目标环境 `caddy validate --config /etc/caddy/Caddyfile` 与真实 HTTPS 联调。不得仅凭配置文件存在勾选域名 / 证书验收。

## 验证与发布包

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/test-ui-math.mjs
node tests/test-match-session.mjs
node --check web/app.js
& .\.venv\Scripts\python.exe scripts/pack-release.py
```

打包前重新校验正式库和模型指纹，生成 `outputs/releases/ringlab-fastapi.zip` 与包内 `release-manifest.json`（逐文件 SHA-256）。包采用白名单，不带原始数据、账号凭据、上传或截图夹具；包含正式库及模型，应作为服务私有材料上传，不能放到静态网站下载目录。输出文件存在时拒绝覆盖，更新时使用 `--output` 指定新版本文件。

并发诊断脚本 `scripts/load-test.py --port PORT --pid PID` 仅访问本机，对指明的临时服务用真实识图夹具发起有限并发；输出 `data/deployment-validation.json`。它需要开发依赖和测试夹具，发行包内不带夹具，因此应在开发环境或完整 QA 工作目录运行。报告包含成功 / 过载数量、延迟、服务进程 RSS / CPU 峰值及结束时健康状态，不包含图片正文或圈位。

公网验收还需：目标 Linux 安装 / 容器构建、真实域名 HTTPS、代理 IP 及来源校验、真实截图上传与连续补圈 / 刷新恢复、目标机器负载、重启恢复。真实样本仍只有一张截图及压缩变体，预测准确率和概率未完成当前排位校准。

## 更新、恢复与回退

每次发布先保留原发行 ZIP、镜像 tag、配置和发布清单；在临时端口启动新版本完成健康 / 示例 / 截图检查，再切换代理或容器。镜像 tag 用版本名，不用同一个 tag 覆盖所有历史。

更新故障时，将 `RINGLAB_RELEASE` 改回已保留的旧版本 tag，使用 `docker compose -f deploy/compose.yaml up -d --no-build` 启动旧镜像，并复查健康接口与预测；对应配置也恢复到旧版本。部署包里的数据 / 模型按发布清单一起恢复，不能只替换模型而混用库。

本次改造前源文件备份位于 `outputs/backups/before-fastapi-20261013.zip`，供本地回退参考；恢复时保留当前版本副本并只替换所需代码文件，不覆盖正式数据 / 训练证据。服务器不存本局记录，重启后浏览器当前标签页的 sessionStorage 圈位仍可再次提交。采集 / 定时任务保持暂停。

技术依据：[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[Uvicorn 配置和可信代理](https://uvicorn.dev/settings/)、[Caddy 请求体限制](https://caddyserver.com/docs/caddyfile/directives/request_body)、[Caddy 反向代理](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)。
