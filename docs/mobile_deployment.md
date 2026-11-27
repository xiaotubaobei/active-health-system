# 手机试用部署

这套配置用于少量用户试用：一个域名同时提供网页和 API，HTTPS 入口由 Caddy 提供，SQLite 数据库和上传文件分别保存在 Docker 卷中。它不会把电脑现有数据库、个人上传视频、申请书或本地数据集打进镜像。实习生的 `a`、`b` 分支不受影响。

目前只准备了配置，尚未在服务器启动，也未完成手机验收。需要一台安装 Docker Engine 和 Compose v2 的 Linux 服务器，以及指向该服务器的域名。开放 TCP 80、443；不要开放数据库、8000 或 5173。服务器须能下载容器镜像和 npm/Python 依赖。

## 首次启动

在服务器项目根目录执行，以下为 Linux shell：

```sh
cp deploy/.env.example deploy/.env
# 编辑 deploy/.env，把 SITE_DOMAIN 改成自己的域名，例如 health.your-domain.cn
# 只填域名，不带协议、路径或端口。
docker compose --env-file deploy/.env -f compose.production.yml config --quiet
docker compose --env-file deploy/.env -f compose.production.yml up -d --build
docker compose --env-file deploy/.env -f compose.production.yml ps
docker compose --env-file deploy/.env -f compose.production.yml logs --tail=100 api web
python3 scripts/check_deployment.py https://你的域名 --camera-assets
```

生产配置与根目录的旧 `docker-compose.yml` 分开使用，不要合并。证书签发需要正确 DNS 和公网可达的 80/443，初次启动可能需要等待。域名变更后重新启动服务。

手机直接访问 `https://你的域名`，先注册个人账号。演示账号默认关闭，登录 Cookie 只通过 HTTPS 传输。手机访问电脑的 `http://局域网IP:5173` 不能代替正式摄像头验收。本方案是手机浏览器网页，支持添加到主屏幕，尚无原生安装包和离线训练功能。离线缓存只用于网页外壳与提示，不缓存个人接口或上传视频。

标准部署的本地视频默认在浏览器内解析，不依赖单独的 RTMPose 服务；视频上限100MB、3分钟，建议先用10～30秒全身动作片段，解析中可取消。浏览器解析只保存姿态数据，不上传本地原视频。独立 AI 评分服务默认未部署；备用结果仍按原规则标记，不计为真实评分。摄像头模型和 WASM 现在由本站提供，手机训练时无需连接 Google Storage 或 jsDelivr。构建前端时会下载固定版本的官方模型（默认 full，约 9.4MB），校验大小和 CRC32C，并从锁定版本的 npm 包复制 WASM；已有正确模型时不会重复下载。构建机器第一次仍需能够访问官方模型地址。模型未加载成功时只有预览，“开始训练”不可用，可关闭摄像头后重试。示范视频也未随镜像打包，首次部署可能没有演示样本。

审核人先注册个人账号，维护人员再在服务器为指定账号设置角色（将示例账号替换为实际账号）：

```sh
docker compose --env-file deploy/.env -f compose.production.yml exec api python /app/scripts/set_user_role.py --username reviewer-name --role physician
```

角色变更后，该账号需重新登录。普通用户仍须明确同意共享资料并填写审核人账号才能送审。

## 手机验收（两台手机、两个个人账号）

1. 分别注册、填写本人基本档案，查看匹配的模板草案。体测换算分可后补，不估填；没有匹配模板时应明确提示。退出后重登，确认资料仍在；账号之间看不到对方记录。
2. 从计划点“练这个动作”，核对动作、组数、次数与计划版本。
3. 打开摄像头，允许权限，确认出现骨架和姿态帧数量。拒绝权限时应提示浏览器及系统权限的恢复方法，可重试；无设备、设备被占用分别提示。普通局域网 HTTP 地址应直接说明需要 HTTPS，不反复请求权限。只有预览画面不算通过。
4. 训练约 30 秒，确认显示采集状态、计时和最近保存时间。支持保持亮屏的浏览器应显示已开启；系统省电或浏览器拒绝时给出提醒和重试入口，不阻止训练。暂停后帧数与计时停止、摄像头关闭、释放亮屏控制，继续后恢复。切到后台自动暂停，回来需手动继续；未开始训练的摄像头预览也应在后台关闭。系统终止相机连接时应暂停并尝试保存到原记录，网络失败需保留未保存提示。刷新并恢复，确认训练编号、已保存帧和计时没有丢失，暂停时间不计入。计时表示摄像头采集时间，不代表动作完成量。
5. 短暂断网，确认保存失败有提示；恢复网络后保存成功。开始请求响应丢失时，在当前页点“重试开始”或刷新同一标签页，应找回同一条训练，不重复建立记录；仍未查到时重新准备原动作的输入，再沿用原请求重试。检查接口也断网时应阻止新建训练。关闭标签页后从训练历史找回，未保存的采集数据无法恢复。未保存前不要关闭页面。
6. 结束训练，打开报告和历史；刷新、重登后仍可回看。备用评分应明确显示“暂无有效评分”。
7. 选择一个10～30秒本地全身动作视频，确认能解析、回放骨架并生成报告。再取消一次解析，确认可重新选择视频；超大文件、超过3分钟的视频、损坏或不支持的视频应明确提示。手机格式不同，优先使用MP4；首次加载模型可能较慢。
8. 管理员在服务器重启服务后，再次登录确认记录与已上传文件仍可访问。

命令行检查验证路由、代理、访问拦截与缓存；加 `--camera-assets` 会实际下载模型并校验清单中的 SHA256、检查 WASM 和脚本，不能替代手机摄像头和浏览器兼容验收。

## Windows 电脑临时手机演示

整合 A 同学的入口后，项目根目录可双击 `启动电脑端.bat` / `关闭电脑端.bat`，或 `启动手机HTTPS.bat` / `关闭手机HTTPS.bat`。两种模式共用 8000/8101 等端口，切换前先停止原模式；脚本不接管其他程序占用的端口。

手机模式使用 `deploy/Caddyfile.mobile`，与 Linux Docker 的 `deploy/Caddyfile` 分开。需要先安装 Node.js、Python 和项目依赖（后端与 `ai_services/pose/requirements.txt`），在项目同级的 `mobile-tools` 目录放置 `caddy.exe`、`cloudflared.exe`。例如项目位于 `C:/work/active-health-system`，工具目录就是 `C:/work/mobile-tools`。工具和模型不提交 Git。

手机脚本会构建网页，以 RTMPose 为本地视频解析方式，启动仅监听本机的 API/姿态服务，再创建临时 HTTPS 隧道。手机、电脑都应打开脚本输出的同一个 HTTPS 地址；该模式开启安全 Cookie，直接打开本机 HTTP 地址不能代替 HTTPS 登录。当前地址和日志在 `runtime_logs/mobile_https/`，停止脚本只处理本次记录的进程并校验启动时间。临时地址可能变化，电脑必须开机联网，不能替代长期部署。

训练页可切换前后摄像头；只有模型就绪并开始采集，才会保存真实姿态帧。切换镜头会先暂停采集。也可点“用手机拍摄视频”调用手机拍摄入口，再按当前配置解析视频；浏览器是否弹出拍摄或选片界面由手机系统决定。服务器解析会上传视频，浏览器解析只保留姿态数据，两者应分别验收。

本次已通过 Caddy 配置校验及本机浏览器流程回归；没有实际启动公网隧道，也没有完成 iPhone/Android 摄像头、RTMPose 真实推理和后台恢复验收。手机测试仍按上面的清单记录设备、浏览器、结果和失败截图。

## 构建机器无法下载模型时

在可访问官方地址的机器执行 `cd frontend && npm ci && npm run prepare:pose`。将生成的 `public/models/pose_landmarker_full.task` 复制到构建机器同一位置，再构建；脚本仍会校验，损坏文件不会进入构建。模型约 9.4MB，不提交 Git。Docker 构建会保留这份准备好的模型，运行文件由容器内 npm 包复制。

本地开发也可指定已有模型（以下为 Windows PowerShell，在 frontend 目录执行）：

```powershell
$env:POSE_MODEL_FILE = 'D:\models\pose_landmarker_full.task'
npm run build
Remove-Item Env:POSE_MODEL_FILE
```

只支持官方 float16 / version 1 文件。默认 full；本地切换 lite/heavy 时须同时设置 `VITE_POSE_LANDMARKER` 并准备对应文件，修改后重新构建。`npm run dev`、`npm run build` 都会先准备资源。公开清单位于 `/pose-assets.json`。

资源依据：[MediaPipe 官方 Web 指南](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/web_js)、[Vite public 目录](https://vite.dev/guide/assets#the-public-directory)。

## 更新、备份与恢复

更新前先备份，确认没有人在训练。下列操作会短暂停止整个网站，防止数据库与视频在备份期间变化。归档含个人资料，放在服务器私有目录，不提交 Git；建议复制到另一台受控设备。归档没有加密，文件哈希用于发现损坏，不能证明备份来自可信人员。

现在提供 `scripts/backup_data.py`，只用 Python 标准库，可执行备份、只读校验、恢复到空目录。数据库使用 SQLite 快照，包含已提交的 WAL 数据；不直接复制正在使用的 `.db`。归档记录文件大小、SHA256、生成时间、代码编号和主要数据表的记录数，生成后自动复核所有文件及数据库完整性。备份失败不留下可被误用的正式归档。数据库快照本身支持 WAL，但数据库与上传文件的整体一致性仍要求停站。

工具只备份数据库及 `uploads` 普通文件，不包含代码、环境变量、HTTPS 证书、模型或演示视频。临时校验和恢复需要可写的临时目录和额外磁盘空间，至少为展开后的数据预留一份空间；容器内校验使用容器的临时磁盘，不是 `/backup` 卷。旧的手工 tar 归档没有清单，不能直接用新工具恢复；保留旧归档，升级到本次代码后先创建一份新备份。

首次使用新工具，先构建包含它的 API 镜像（构建不会替换正在运行的服务）。以后日常备份无需每次构建：

```sh
docker compose --env-file deploy/.env -f compose.production.yml build api
```

备份步骤：

```sh
mkdir -p backups
chmod 700 backups
docker compose --env-file deploy/.env -f compose.production.yml stop
docker compose --env-file deploy/.env -f compose.production.yml run --rm --no-deps -v "$PWD/backups:/backup" api python /app/scripts/backup_data.py create --output-dir /backup --label "$(git rev-parse HEAD)"
docker compose --env-file deploy/.env -f compose.production.yml start
```

备份命令失败时也先执行上面的 `start` 恢复站点，排查原因后重新备份，不接着更新。成功时会输出实际归档文件名。可随时独立复核，把下面文件名替换为实际文件名；只读校验不需要停站：

```sh
docker compose --env-file deploy/.env -f compose.production.yml run --rm --no-deps -v "$PWD/backups:/backup:ro" api python /app/scripts/backup_data.py verify /backup/health-实际文件名.tar.gz
```

确认备份命令成功，并记录备份对应的完整代码编号后再更新：

```sh
git pull --ff-only
docker compose --env-file deploy/.env -f compose.production.yml up -d --build
python3 scripts/check_deployment.py https://你的域名 --camera-assets
```

普通 `stop`、`down` 和重建镜像保留数据卷；**不要使用 `down -v`**，它会删除持久数据。首次生产部署使用全新数据库，不会自动迁入本机旧数据。

### 恢复到新数据卷

工具不会覆盖非空数据库目录或上传目录。恢复前完整校验归档、文件路径、每个文件哈希和 SQLite 完整性；校验失败时不会写目标数据卷。不解压符号链接、硬链接、越界路径或重复文件。复制中途出错会清理本次已创建的文件，不能代替停站和磁盘容量检查。

先完成上面的 `verify`，停站并保留原项目及原数据卷，在维护窗口使用备份清单 `label` 中记录的代码版本。可在单独克隆中检出该版本，复制受控的 `deploy/.env` 并构建镜像。以下命令在该代码目录执行，使用一个**此前没有使用过的**项目名 `active-health-restored` 创建新数据卷；如该名称已有数据，改用新的名称。不要删除或清空原来的卷：

```sh
# 在原部署目录停止原站点，确认没有其他进程写入原数据。
docker compose --env-file deploy/.env -f compose.production.yml stop

# 在备份对应代码目录执行；将备份目录改为实际绝对路径。
docker compose -p active-health-restored --env-file deploy/.env -f compose.production.yml build
docker compose -p active-health-restored --env-file deploy/.env -f compose.production.yml run --rm --no-deps -v "/实际备份目录:/backup:ro" api python /app/scripts/backup_data.py restore /backup/health-实际文件名.tar.gz

# 仅在恢复命令成功后启动新站点。
docker compose -p active-health-restored --env-file deploy/.env -f compose.production.yml up -d
python3 scripts/check_deployment.py https://你的域名 --camera-assets
```

新项目的证书数据卷也是全新的，需要重新完成证书签发。原项目停止后才能使用相同的 80/443 端口。不要同时启动原站点和恢复站点。新站点验收完成前，原项目和原卷继续保留；若恢复失败，停止新项目，在原目录按原代码版本启动原项目。切换后若新站点已有新数据，不要直接切回旧卷，以免漏掉新记录。后续更新、备份和查看日志均须继续带 `-p active-health-restored`，否则操作到的是原项目。

除命令行检查外，还需登录自己的测试账号，核对档案、计划、历史、旧报告、未完成训练和上传文件；换另一个账号确认仍不能查看别人的资料。代码回退不会自动回退数据库结构。需要迁移到 PostgreSQL 时须另做备份方案，本工具只支持本方案中的 SQLite。

### 本机恢复演练

工具也可在 Windows 使用，必须明确提供本机路径。下例只展示参数，先停止后端；数据库/上传路径应替换为**待备份的真实位置**，恢复位置须是新的空目录，不要指向当前项目：

```powershell
.venv/Scripts/python.exe scripts/backup_data.py create --database C:/数据目录/active_health.db --uploads C:/数据目录/uploads --output-dir C:/备份目录 --label 本次代码编号
.venv/Scripts/python.exe scripts/backup_data.py verify C:/备份目录/实际文件名.tar.gz
.venv/Scripts/python.exe scripts/backup_data.py restore C:/备份目录/实际文件名.tar.gz --storage C:/恢复演练/storage --uploads C:/恢复演练/uploads
```

自动恢复检查使用临时数据库和虚构账号，覆盖恢复后登录、旧报告、未完成训练继续保存、账号隔离和文件字节恢复，以及 WAL、损坏归档、越界路径、非空目标和复制中断。它不等于服务器 Docker 已启动或手机验收通过。

配置依据：[Caddy 路径代理](https://caddyserver.com/docs/caddyfile/directives/handle_path)、[页面回退](https://caddyserver.com/docs/caddyfile/directives/try_files)、[Compose 健康检查启动顺序](https://docs.docker.com/compose/how-tos/startup-order)。
