# 部署自己的 HiAgent 工作区

这是可选路线：启用网页上传、异步分析和分享链接。需要自己的 AWS 账号、CLI v2、Node.js 22+，并完成[Python 环境与视觉模型安装](setup.md)。原比赛账号和 CloudFront 地址均不再使用。

## 准备与部署

以下命令在 `hidden-impact/` 中执行，先激活 `.venv`：

```bash
export AWS_PROFILE=hiagent
export AWS_REGION=us-east-1
export HIAGENT_MODEL_ID=qwen.qwen3-vl-235b-a22b
npm ci --prefix infra
python -m pip install --target cloud/agent/vendor -r cloud/agent/requirements.txt
python scripts/prepare_vision.py
aws sts get-caller-identity
```

`prepare_vision.py` 为 Lambda 构建 Linux ARM64 / Python 3.13 视觉与编码依赖；不使用本机 macOS 二进制。模型在部署成功后上传到你自己的私有 S3。

**新账号 / 区域首次使用 CDK 时**执行 bootstrap；已初始化则跳过：

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
(cd infra && npx cdk bootstrap "aws://$ACCOUNT_ID/$AWS_REGION")
python scripts/deploy.py
```

部署者需要创建 CloudFormation、IAM、S3、Lambda、API Gateway、AgentCore 和 CloudFront 资源的权限；运行时调用权限由 CDK 配置。默认基础模型需在选定区域可用；当前 IAM 模型策略按区域基础模型 ARN 生成，跨区域推理 profile 需要额外调整策略。账号需允许 Lambda 并发预留（工作进程 2、API 5）。部署和模型调用会计费。

输出地址见 `infra/cdk-outputs.json`；工作区访问码保存为 `.team-access-code`。打开网站会进入上传工作台，连接工作区后上传视频和配套 JSON，等待任务完成，再进入回放。可用 `python server.py --cloud` 从本地页面访问这套部署。

## 配置

| 变量 / 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `AWS_PROFILE` / `--profile` | 标准凭证链 | 自己的 AWS 身份 |
| `AWS_REGION` / `--region` | `us-east-1` | 自己的可用区域 |
| `HIAGENT_MODEL_ID` | `qwen.qwen3-vl-235b-a22b` | Converse 视觉模型 |
| `HIAGENT_STACK_NAME` / `--stack` | `HiAgent` | CloudFormation 栈名称 |
| `HIAGENT_RUNTIME_NAME` | `hiagent_video` | 账号 / 区域内唯一的 AgentCore 名称 |
| `HIAGENT_PERMISSIONS_BOUNDARY` | 无 | 组织要求的 IAM 边界策略名称 |
| `HIAGENT_REFERENCE_DIR` | 无 | 可选、明确提供的参考校准文件目录 |

部署不附带赛事权限边界，也不默认上传历史示例参考。参考目录中的文件需符合 `reference-profile-v1`，并按源视频 SHA-256 命名；复用仍要求视频指纹与出手记录匹配。凭证、访问码、模型权重和本地输出不提交 Git。

## 验证、复核与发布

先在工作台真实分析一次视频。`python scripts/smoke_release.py --api-only --job JOB_ID` 可检查任务结果、成片与故事帧；遇到错误查看任务返回值和 CloudWatch 日志。

独立 Reviewer：

```bash
python scripts/review_result.py --source-job JOB_ID --strategy vlm --wait
```

需公开分享时，在源视频的素材记录中保存合法来源与发布依据，再执行：

```bash
python scripts/publish_result.py --job JOB_ID
python scripts/smoke_release.py --public-only
```

发布器将成片与故事帧复制为持久化网站资源，首页直接显示结果；不会把临时签名链接当成长期地址。请先确认对应素材允许公开发布。

不再使用时，在 `infra/` 执行 `npx cdk destroy HiAgent`。S3 桶使用保留策略，删除栈后仍可能产生存储费用；备份后在自己的账号单独清理。项目不会自动删除你的媒体。
