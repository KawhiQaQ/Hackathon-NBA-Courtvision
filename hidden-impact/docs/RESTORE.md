# 开发与部署

本页供项目维护和新环境安装使用，不是额外的比赛提交要求。观看已发布作品不需要安装依赖、下载模型或提供 AWS 凭证。

## 准备环境

需要 Python 3.12+、Node.js/npm、AWS CLI v2。从仓库根目录执行：

```sh
npm ci --prefix aws-preflight
python3 -m venv hidden-impact/.venv
hidden-impact/.venv/bin/python -m pip install -r hidden-impact/requirements.txt
hidden-impact/.venv/bin/python -m pip install --target hidden-impact/cloud/agent/vendor -r hidden-impact/cloud/agent/requirements.txt
hidden-impact/.venv/bin/python hidden-impact/scripts/prepare_vision.py
```

`prepare_vision.py` 准备 Lambda 使用的 Linux ARM64 依赖和 FFmpeg。AgentCore 的 vendor、视觉 layer 和模型大文件由部署前检查验证。

## 模型与媒体

Qwen3-VL 通过 Amazon Bedrock 调用，无需获取其权重。篮球视觉检测使用独立 ONNX 模型，由本队私有 S3 保存；来源、版本和 SHA-256 在 `models/basketball/` 中记录。

如本机缺少视觉权重，可从本队现有 MediaBucket 恢复：

```sh
cd hidden-impact
.venv/bin/python scripts/restore_models.py --bucket <本队MediaBucket>
```

若云资源已清理，使用保留的本地资产或私有备份。Git 不包含原视频及权重。模型许可见 [模型来源](../models/basketball/SOURCES.txt)；素材来源随导入记录保存。

## 登录与部署

按主办方当前账号配置 `nba-sso` 和 `nba` 两个 AWS profile。资源只部署在 `us-east-1`；主办方已完成初始化，**不要运行 cdk bootstrap**。

```sh
aws sso login --profile nba-sso
aws sts get-caller-identity --profile nba --region us-east-1
.venv/bin/python scripts/deploy.py
```

`infra/cdk.json` 包含 `NBAHackathonParticipantBoundary` 权限边界。部署脚本读取当前账号、检查资产、部署设施并上传视觉模型。输出写入 `infra/cdk-outputs.json`，本地服务配置随之更新。

团队访问码保存在本机 `.team-access-code`，不提交 Git。公开作品页无需认证；上传和分析需要团队认证。新账号的 Bedrock 模型权限与服务配额由 AWS 和赛事账号配置决定。

## 导入与发布

以下示例使用独行侠官方考试素材（北京时间 2025-12-07）：

```sh
.venv/bin/python scripts/ingest_official.py --video ../double.mp4 --id dallas-exam --game 0022500356 --player 1631108 --event 273 --source https://du5imhgxabl0d.cloudfront.net/portal --companion ../double.companion.json --out data/frames/official/dallas-exam-request.json
.venv/bin/python scripts/smoke_release.py --api-only --request data/frames/official/dallas-exam-request.json
.venv/bin/python scripts/publish_result.py --job <成功任务ID>
.venv/bin/python scripts/smoke_release.py --public-only
```

导入新视频时更新比赛、球员、事件与出手时间，不能沿用示例的对应关系。未提供时间对齐时显示回合摘要。云分析会实际调用模型并消耗 AWS 用量。

发布器将已完成任务的成片、原视频和故事帧复制为持久化网站资源，并更新默认结果入口。它保留结果来源，不使用即将过期的签名链接作为公开发布地址，也不操作赛事提交表单。

## 验证

在 `hidden-impact/` 中执行：

```sh
.venv/bin/python -m unittest discover -s tests
node tests/test_web_render.cjs
node tests/test_game_view.cjs
node tests/test_generated_showcase.cjs
node tests/test_showcase_insights.cjs
node tests/test_actor_insights.cjs
node tests/test_story_playback.cjs
node tests/test_studio_flow.cjs
```

离线回归覆盖逻辑与媒体生成；`smoke_release.py` 用于另行验证真实云端调用。新任务失败时读取任务错误，不把离线测试通过当作云端推理成功。

## 私有快照

`scripts/cloud_snapshot.py` 支持备份校验与恢复，格式见 [snapshot-schema](snapshot-schema.md)。恢复时显式指定新桶，不复用旧部署 ID；备份及私有配置保持在 Git 之外。

### 模型 Reviewer

对原始分析创建独立复核任务：`POST /api/reviews`，请求体为 `{"sourceJob":"已完成的原始任务ID"}`，使用现有 `X-Team-Key`。也支持 `sourceAnalysis` 指向已保存的原始分析记录。通过 `GET /api/jobs/{id}` 查询状态、播放结果和下载地址；复核不会自动替换首页作品。

```sh
.venv/bin/python scripts/review_result.py --source-job <任务ID> --wait --out verification/reviewer
```

Reviewer 重新抽取原视频、调用 Bedrock VLM 核对检测框中的固定角色，并结合画面和深度数据复核解说草稿。输出 `review.json`（标准角色锚点与故事计划）、`references.json`（角色参考框）、`review-report.json`（模型调用、覆盖率及来源）和 `presentation-plan.json`，随后使用共用渲染器生成视频与故事帧。原始评分保持不变；无法定位的位置留空。人工编辑与模型复核使用相同结构，各自保留实际来源。
