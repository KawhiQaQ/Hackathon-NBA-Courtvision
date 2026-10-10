# AWS 连通性检查栈

可选的最小检查工具，用于验证赛事 CDK 权限边界、S3、CloudFront、HTTP API 和 AgentCore 连通性。正式产品部署见 [Hidden Impact](../hidden-impact/docs/RESTORE.md)。

此目录的 `package-lock.json` 同时提供正式项目使用的锁定版 CDK 依赖；不要删除。

## 使用

按当前赛事账号配置 AWS profile 后，在本目录执行：

```sh
aws sso login --profile nba-sso
aws sts get-caller-identity --profile nba --region us-east-1
npm ci
npm run synth
npm run diff
npm run deploy
```

资源部署在 `us-east-1`；保留 `NBAHackathonParticipantBoundary`，不要执行 `cdk bootstrap`。最新地址取自本地部署输出，不使用历史账号的资源地址。

## 检查范围

浏览器 → CloudFront → API Gateway → Lambda → AgentCore → JSON。

请求使用随机 nonce 核对实际响应。该栈仅检查连通性，不调用模型、不分析视频；完整业务验证使用正式项目的 `scripts/smoke_release.py`。部署与调用会产生 AWS 用量。
