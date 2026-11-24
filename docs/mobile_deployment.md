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

手机直接访问 `https://你的域名`，先注册个人账号。演示账号默认关闭，登录 Cookie 只通过 HTTPS 传输。手机访问电脑的 `http://局域网IP:5173` 不能代替正式摄像头验收。本方案是手机浏览器网页，尚无安装包和离线训练功能。

标准部署的本地视频默认在浏览器内解析，不依赖单独的 RTMPose 服务；视频上限100MB、3分钟，建议先用10～30秒全身动作片段，解析中可取消。浏览器解析只保存姿态数据，不上传本地原视频。独立 AI 评分服务默认未部署；备用结果仍按原规则标记，不计为真实评分。摄像头模型和 WASM 现在由本站提供，手机训练时无需连接 Google Storage 或 jsDelivr。构建前端时会下载固定版本的官方模型（默认 full，约 9.4MB），校验大小和 CRC32C，并从锁定版本的 npm 包复制 WASM；已有正确模型时不会重复下载。构建机器第一次仍需能够访问官方模型地址。模型未加载成功时只有预览，“开始训练”不可用，可关闭摄像头后重试。示范视频也未随镜像打包，首次部署可能没有演示样本。

审核人先注册个人账号，维护人员再在服务器为指定账号设置角色（将示例账号替换为实际账号）：

```sh
docker compose --env-file deploy/.env -f compose.production.yml exec api python /app/scripts/set_user_role.py --username reviewer-name --role physician
```

角色变更后，该账号需重新登录。普通用户仍须明确同意共享资料并填写审核人账号才能送审。

## 手机验收（两台手机、两个个人账号）

1. 分别注册、首次测评、生成计划。退出后重登，确认资料仍在；账号之间看不到对方记录。
2. 从计划点“练这个动作”，核对动作、组数、次数与计划版本。
3. 打开摄像头，允许权限，确认出现骨架和姿态帧数量。拒绝权限时应有错误提示，可重试；只有预览画面不算通过。
4. 训练约 30 秒，确认显示采集状态、计时和最近保存时间。暂停后帧数与计时停止、摄像头关闭，继续后恢复。切到后台自动暂停，回来需手动继续。刷新并恢复，确认训练编号、已保存帧和计时没有丢失，暂停时间不计入。计时表示摄像头采集时间，不代表动作完成量。
5. 短暂断网，确认保存失败有提示；恢复网络后保存成功。开始请求响应丢失时，在当前页点“重试开始”，应找回同一条训练，不重复建立记录；此保护不覆盖刷新后重新点开始。未保存前不要关闭页面。
6. 结束训练，打开报告和历史；刷新、重登后仍可回看。备用评分应明确显示“暂无有效评分”。
7. 选择一个10～30秒本地全身动作视频，确认能解析、回放骨架并生成报告。再取消一次解析，确认可重新选择视频；超大文件、超过3分钟的视频、损坏或不支持的视频应明确提示。手机格式不同，优先使用MP4；首次加载模型可能较慢。
8. 管理员在服务器重启服务后，再次登录确认记录与已上传文件仍可访问。

命令行检查验证路由、代理、访问拦截与缓存；加 `--camera-assets` 会实际下载模型并校验清单中的 SHA256、检查 WASM 和脚本，不能替代手机摄像头和浏览器兼容验收。

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

更新前先备份，确认没有人在训练。下列备份会短暂停止整个网站，防止数据库与视频在备份期间变化。归档含个人资料，放在服务器私有目录，不提交 Git；建议复制到另一台受控设备。

```sh
mkdir -p backups
chmod 700 backups
docker compose --env-file deploy/.env -f compose.production.yml stop
docker compose --env-file deploy/.env -f compose.production.yml run --rm --no-deps -v "$PWD/backups:/backup" api python -c 'import tarfile, datetime; name="/backup/health-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")+".tar.gz"; t=tarfile.open(name,"w:gz"); t.add("/app/storage",arcname="storage"); t.add("/app/uploads",arcname="uploads"); t.close(); print(name)'
docker compose --env-file deploy/.env -f compose.production.yml start
```

确认备份命令成功并检查归档后再更新：

```sh
git pull --ff-only
docker compose --env-file deploy/.env -f compose.production.yml up -d --build
python3 scripts/check_deployment.py https://你的域名 --camera-assets
```

普通 `stop`、`down` 和重建镜像保留数据卷；**不要使用 `down -v`**，它会删除持久数据。首次生产部署使用全新数据库，不会自动迁入本机旧数据。

恢复时先停站，保留当前数据卷副本，再在维护窗口将已核对的备份中 `storage/` 和 `uploads/` 内容分别恢复到对应卷。使用备份时的代码版本启动并完成上述验收。不要直接覆盖正在运行的 SQLite 文件；代码回退不会自动回退数据库结构。

配置依据：[Caddy 路径代理](https://caddyserver.com/docs/caddyfile/directives/handle_path)、[页面回退](https://caddyserver.com/docs/caddyfile/directives/try_files)、[Compose 健康检查启动顺序](https://docs.docker.com/compose/how-tos/startup-order)。
