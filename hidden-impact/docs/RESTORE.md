# AWS 清理后的恢复

本说明对应北京时间 2026-10-08 凌晨的代码。赛事资源预计当日 09:00 暂停并清理；旧 CloudFront 地址、桶名、AgentCore ARN 不保证继续存在。

## 已保存在哪里

- GitHub 私有仓库：完整前端、视觉/评分算法、AgentCore/API、CDK、依赖锁定、离线回归测试及脱敏测试样本。
- 本机仓库根目录 `backups/aws-2026-10-08/`：赛事 Media S3 的全量对象和 SHA-256 清单，包括模型 ONNX、示例/上传视频、配套数据、检测缓存、历史分析与导出 MP4。
- 同一备份的 `private-config/`：旧部署输出、本地代理配置与团队访问码，仅作私有恢复参考。此目录不得提交 Git。
- 本机 `hidden-impact/models/basketball/` 保留原始 PT/ONNX；`data/videos/` 保留本地视频；`verification/` 保留完整研发记录。这些大文件不在 Git 中。

Git 仓库不是视频/权重备份。请保留本机的 `backups/`；仅重新 clone 仓库，无法自动找回原上传视频。原始比赛素材与模型许可归对应权利方，不发布模型或视频为自有作品。

## 1. 准备源码与依赖

需要 Python 3.12+、Node.js/npm、AWS CLI v2。克隆后在仓库根目录执行：

```sh
npm ci --prefix aws-preflight
python3 -m venv hidden-impact/.venv
hidden-impact/.venv/bin/python -m pip install -r hidden-impact/requirements.txt
hidden-impact/.venv/bin/python -m pip install --target hidden-impact/cloud/agent/vendor -r hidden-impact/cloud/agent/requirements.txt
hidden-impact/.venv/bin/python hidden-impact/scripts/prepare_vision.py
```

最后一步下载固定版本的 Python 3.13 / ARM64 Lambda 依赖及 FFmpeg，生成被 Git 忽略的 `cloud/vision-layer/`。它仍附带旧 YOLOX 兼容模型；当前篮球专用模型从 Media S3 的 `models/basketball-v1/` 读取。

在原电脑上这些依赖和 layer 已存在，无需重复下载。AgentCore 中的业务模块在 `cloud/agent/`，API 兼容副本在 `cloud/api/`，修改公共算法时同步两处。

## 2. 等主办方重新开放登录

按新的赛事账号重新配置 `nba-sso` 和 `nba` 两个 AWS profile。不要盲用旧账号 ID / Role ARN。

```sh
aws sso login --profile nba-sso
aws sts get-caller-identity --profile nba --region us-east-1
```

- 只部署 `us-east-1`。
- **不要执行 `cdk bootstrap`**。以主办方届时已初始化的环境为准。
- `infra/cdk.json` 保留 `NBAHackathonParticipantBoundary` 权限边界。
- CDK 使用 profile 的目标账号 (`CDK_DEFAULT_ACCOUNT`)；核对上一条命令输出确为比赛团队账号。
- 确认比赛账号仍允许 `qwen.qwen3-vl-235b-a22b` 与 AgentCore。服务白名单或配额变化不是恢复代码能自动消除的。

## 3. 重建设施

```sh
cd hidden-impact
.venv/bin/python scripts/deploy.py
```

脚本使用相邻 `aws-preflight/node_modules` 中锁定的 CDK。没有本地团队访问码时自动生成新的私有访问码；部署成功后保存 `infra/cdk-outputs.json`，并自动更新 `.cloud-config.json` 为新的前端地址。无需复制旧 ARN、分发 ID 或 URL。

部署脚本现在会先校验本机模型、AgentCore vendor、Linux ARM64 视觉依赖、FFmpeg 和中文字体，并检查 Lambda 解压包总量（代码＋layer，250 MiB 上限）。CDK 成功后自动向新 MediaBucket 上传三份篮球 ONNX 模型，并按 SHA-256 元数据与文件大小核对；相同文件不重复上传。缺少资产、SSO 或目标账号权限时明确失败，不会将只创建了设施视为模型已可用。

此步骤会实际创建并计费：S3、CloudFront、HTTP API、Lambda（工作实例 8GB / 15分钟）、AgentCore、日志。现在不需要提前执行重建。

## 4. 恢复私有媒体与模型

从仓库根目录执行，`--bucket` 必须填**新部署输出 MediaBucket**，不是旧桶名：

```sh
hidden-impact/.venv/bin/python hidden-impact/scripts/cloud_snapshot.py verify backups/aws-2026-10-08
hidden-impact/.venv/bin/python hidden-impact/scripts/cloud_snapshot.py restore backups/aws-2026-10-08 --bucket NEW_MEDIA_BUCKET
```

恢复器先校验所有文件，再上传；不会创建桶或删除目标桶已有对象。同 key 对象会被写入备份版本，因此面向新部署的空桶使用。备份清单中的 sourceBucket 仅供追溯，恢复必须显式指定目标。

`.team-access-code` 可沿用本机文件；若使用新机器，建议由 deploy.py 生成新码。不要把旧 `.cloud-config.json` 覆盖回新部署配置。

如果本地全量备份丢失：模型来源记录见 `models/basketball/SOURCES.txt`，但重新下载/导出与第三方链接可用性须另行验证。公开示例可尝试 `scripts/build_nba_samples.py` 和 `scripts/publish_nba.py` 重建；不能据此恢复私人上传或历史结果。

## 5. 验证恢复

```sh
cd hidden-impact
.venv/bin/python -m unittest discover -s tests
node tests/test_web_render.cjs
.venv/bin/python server.py --port 8765
```

浏览器打开 `http://127.0.0.1:8765/`，主动导入视频并分析。验证模型加载、AgentCore/VLM 调用、视频播放及角色/时间轴交互。回归测试不产生云调用费用；真正点击分析会产生云资源/模型费用。

旧浏览器项目和导出 JSON 可辅助找回 job ID；对象恢复后 API 会重新签发媒体 URL。旧 presigned URL 过期属正常现象，不能直接拿旧链接判断恢复失败。

## 当前质量限制

`temporal-impact-v5` + `focused-outcome-v2` 已把后续出手检查和举球释放动作冲突检查加入候选核验。VLM 仍可能错认球员、持球者和投篮者；阈值为工程规则，未经教练标注集校准。2026-10-08 上传示例的 P1 已退出排名，尚未产生通过全部核验的替代 MVP。不要把管线能运行或测试通过等同于篮球归因准确率达标。

## 同场多回合结果（2026-10-10）

默认作品入口读取 `web/demo/game.json`，包含同一场 `0042500404` 的五段尼克斯进攻。静态部署需完整上传 `web/`，包括 `demo/game/` 的视频、关键帧和单回合 manifest。历史单回合展示仍可单独访问。当前五回合使用人工复核的身份、故事文本与篮球检测模型校准的位置；来源保存在 manifest 和 `data/review-archive/game/`，不能作为五次新 VLM 调用的证明。

真实工作流在工作台一次选择多个视频，逐个调用现有 `/api/jobs` 流程；每个结果包含分阶段 `narration`、`presentation`、动态 MP4 和故事帧。点击“汇总本场 MVP”，确认比赛、进攻队与主角球衣号码，再调用 `POST /api/games`。请求包含 `gameId`、`team`、`jobIds` 和可选的 `identities: {jobId: jersey}`。服务端重新读取已核验的任务结果、刷新媒体签名、计算分数并保存任务引用；`GET /api/games/{id}` 返回可直接由 `/?game={id}` 展示的完整汇总。比赛与球队不一致会被拒绝，相同 `roundKey` 仅计一次；无法确认号码的回合保留回放但不合并排名。未提供赛事回合 ID 时使用视频 ID，无法据此识别内容相同但 ID 不同的二次上传。

回合分是动作证据 65%＋出手机会质量 20%＋相对同场同球员同类出手表现 15%；对照缺失时按可用权重归一化。比赛综合指数是总贡献占比 60%＋个人平均回合分 25%＋回合 MVP 次数占比 15%。这是版本化的观察指标，不是经标注比赛校准的个人因果价值模型；命中结果不加分，均分只统计当选回合，统计范围是上传的回合集合。阶段汇总 Gravity 保留为背景画像，不伪装成逐回合引力。

没有 tracking 时，配套 JSON 仍可提供 `shotContext`（比赛、球队、出手者、预期命中率和同场出手列表），见 `web/data/shot-context-example.json` 的结构示例。其中示例数值不能作为真实比赛数据使用。身份映射可通过 companion-v2 的 `players[].jersey` 提供，也可在汇总对话框确认。上传配套数据的预期命中率显示为“配套数据预期命中率”，不会自动标为官方数据。

本地通用导出：`python scripts/export_game.py --project project.json --out web/results/my-game`。项目文件结构：`{gameId, team, rounds: [{analysis, video, jersey}]}`，文件路径相对项目 JSON；输出页为 `/?result=results/my-game/game.json`。此入口实际使用通用分析结果、评分和渲染函数，不读取演示球员编号。

本地离线工作台可载入五个现成样例并汇总，`/api/game-summary` 与云端共用聚合函数；新上传视频在未启用云端时只能预览，不会伪造 VLM 结果。静态样例由 `scripts/build_game_showcase.py` 重建，需要原视频与首回合审阅存档；其余四回合的位置来自 `scripts/reviewed_role_paths.py` 的身份复核锚点，已经不使用逐帧最近检测框重绑定。`cdk deploy` 恢复后再验证真实 AWS 权限与在线模型响应；此次本地测试不代表云端已部署。

五回合统一使用 `cloud/api/render_video.py` 的 `locked-trio-v2` 合成器：固定三角色标牌、主角方向箭头、柔化聚焦和底部角色栏，不绘制脚底光圈。人物出画或切到替补席时保留角色栏，不将标注移给其他人。通用视觉流程和样例构建均加入背景相位相关的镜头平移补偿，仅修正箭头方向，不改变球员位置或评分。此次检查通过 120 项 Python 测试、4 组 Node 前端测试及五回合 39 个本地 HTTP 资源验证。


## 发布前复核（2026-10-10）

本轮修复队列提交失败后卡在排队、过期任务被缓存复用、异常处理依赖 Lambda context、单次摘要解说失败拖垮整个结果，以及上传时长/完整性校验不足。工作台等待窗口与 15 分钟 worker 相适配，渲染阶段有单独状态。API 与 AgentCore 共用的六份算法模块进行了逐字节一致性检查。

离线验证：118 项 Python 测试、4 组 Node 前端测试通过，涵盖真实 MP4 渲染、任务结果签名、分段解说、游戏汇总、失败重试；AWS 客户端在这些测试中使用替身，不能证明云端权限已恢复。CDK `synth --no-lookups` 成功，4 个 IAM 角色均带赛事权限边界；当前 Lambda 代码与 layer 解压总大小约 229 MiB。五回合展示的 39 个页面/媒体资源通过本地 HTTP 检查。

本次 SSO 登录成功，但原团队角色 `NBAHackathonParticipantRole` 的 `sts:AssumeRole` 返回 AccessDenied，故尚未完成重新部署及真实 Bedrock / AgentCore 端到端调用。需以赛事门户重新开放后的 profile 为准。

权限恢复后：

```sh
.venv/bin/python scripts/deploy.py
.venv/bin/python scripts/publish_nba.py
.venv/bin/python scripts/smoke_release.py
.venv/bin/python scripts/smoke_release.py --request data/frames/nba-public/nba-0042500404-197-request.json
```

最后一条会创建真实分析任务并产生 AWS 用量；验证分段解说、渲染视频、故事关键帧和 `/api/games`，输出保存在被 Git 忽略的 `verification/cloud-release-smoke.json`。它不改写演示结果。新素材尚未形成有效候选时检查会明确失败，不把“任务完成”冒充完整展示成功。

仅检查本地静态入口可执行：

```sh
.venv/bin/python scripts/smoke_release.py --url http://127.0.0.1:8765 --public-only
```
