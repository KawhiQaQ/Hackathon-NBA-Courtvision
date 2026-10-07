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
