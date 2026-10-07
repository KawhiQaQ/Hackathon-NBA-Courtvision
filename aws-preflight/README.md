# NBA 赛事 AWS 赛前部署检查

独立的最小测试栈，用于验证 CDK、赛事 IAM 权限边界、私有 S3、CloudFront 前端发布和 AgentCore Runtime 实际调用。它是连通性探针，没有接入模型或比赛数据，未提交到赛事 Portal。

## 实测结果（北京时间 2026-10-06 23:24）

- CDK 部署成功；首次部署 `CREATE_COMPLETE`，接入 AgentCore 后为 `UPDATE_COMPLETE`。
- 实际创建的 AgentCore 和 Lambda IAM 角色均已绑定 `NBAHackathonParticipantBoundary`，通过 IAM 只读查询核实。
- CloudFront 分发 `E3RSPDLK77FS9Y` 状态为 `Deployed`。
- 页面地址：<https://d2rbexi7m51u3i.cloudfront.net/>
- HTTPS GET 返回 `HTTP/2 200`、`content-type: text/html`，响应经过 CloudFront。
- AgentCore Runtime `nba_team14_preflight-IJp5q2Fnvg` 状态 `READY`，Python 3.13 代码包直接部署，无需 Docker 或 GPU。
- AWS CLI 直接调用 Runtime 返回 HTTP 200，返回随机实例 ID、时间与原样 nonce；显式停止测试会话返回 200。
- CloudFront `POST /api/agent` 返回 HTTP 200，实测全请求耗时 3.65 秒，其中代理记录 AgentCore 调用耗时 2021 ms；请求的 nonce 与云端响应一致，响应禁止缓存。
- Chrome 点击「验证 AgentCore 云端调用」，显示「验证通过 · AgentCore 已真实返回结果」。该次调用耗时 1324 ms，返回时间为 `2026-10-06 23:24:23`（北京时间），请求编号 `f7b1135a-7a54-4b9a-b94a-84379fa013f1`。
- 接口收到不支持的 `action=invoke-model` 返回 HTTP 400，没有发起模型推理。
- CloudWatch 日志与浏览器请求编号吻合；两次代理调用均成功结束，没有调用或会话释放错误。
- Claude Sonnet 4.6 与 Qwen3-VL 的授权状态均为 `AUTHORIZED`，协议、权益、区域检查均为 `AVAILABLE`。
- Claude 推理配置 `global.anthropic.claude-sonnet-4-6` 为 `ACTIVE`；未调用任何模型推理。

## 环境

- AWS profile：`nba`；登录 profile：`nba-sso`
- 账号：`214299441669`；区域：`us-east-1`
- 栈名：`NbaTeam14Preflight`
- AWS CLI v2 安装于 `~/.local/aws-cli/aws`，链接位于 `~/.local/bin/aws`
- CDK 和库版本锁定在 `package-lock.json`
- `cdk.json` 已包含 `NBAHackathonParticipantBoundary`
- 主办方已经 bootstrap；**不要运行 `cdk bootstrap`**

## 登录及部署

在本目录运行：

```sh
~/.local/bin/aws sso login --profile nba-sso
~/.local/bin/aws sts get-caller-identity --profile nba --region us-east-1
npm ci
npm run synth
npm run diff
npm run deploy
```

页面源文件在 `web/index.html`，部署结果在本地 `cdk-outputs.json`。

## 已验证的调用链

浏览器 → CloudFront `/api/agent` → API Gateway HTTP API → Lambda → AgentCore Runtime → JSON 返回页面。

- `agent/main.py`：只依赖 Python 标准库，实现 `/ping` 健康检查和 `/invocations` 请求处理。
- `api/handler.py`：验证输入，以 IAM 身份调用本栈 Runtime，在完成后调用 `StopRuntimeSession` 释放会话。AWS 凭证不会发送到浏览器。
- `app.js`：统一管理 AgentCore、代理接口与前端部署。所有资源位于赛事账号 `214299441669`、区域 `us-east-1`。
- 页面按钮每次生成随机 nonce 并核对云端原样返回，避免将静态页面或缓存响应误判为调用成功。
- API 是公开的固定功能连通性检查，仅接受 `action=ping` 和长度不超过 64 的 nonce；速率限制 1 请求/秒、突发 2，Lambda 并发限制 2。接入正式业务前应另行设计用户认证和额度控制。

验证响应及日志保存在本地 `verification/`，已由根目录 `.gitignore` 排除。

参考 AWS 文档：[Python 代码直接部署](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy-python.html)、[HTTP 协议](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html)。

## 资源与费用范围

CDK 创建私有 S3 桶、CloudFront Distribution/OAC、AgentCore Runtime、API Gateway、代理 Lambda、日志组，以及上传静态文件所需的 Lambda 和带权限边界的 IAM 角色。S3 阻止公网直接访问，仅允许指定 CloudFront 分发读取页面。没有创建 GPU、EC2、NAT Gateway 或模型推理端点。

资源仍适用 AWS 存储、请求、流量及执行计费，包括 AgentCore；赛事额度是否抵扣未确认。本次未调用模型推理，未接受新的模型市场协议。代理完成请求后主动释放会话；兜底空闲超时 60 秒，会话最大生命周期 300 秒。接口保留供后续检查使用，点击按钮仍会触发一次真实云端执行。

删除测试栈可使用 `npx cdk destroy --profile nba`。S3 桶采用 `RETAIN`，销毁栈后需另行核对并清理保留的测试桶；bootstrap 资产和日志也可能保留。不要删除主办方的 CDKToolkit 栈或其他共享资源。

## 模型检查范围

使用 Bedrock `get-foundation-model-availability` 查询 Claude Sonnet 4.6 和 Qwen3-VL 235B A22B 的账号授权及区域可用性；另查询 Claude 的 `global.anthropic.claude-sonnet-4-6` 推理配置状态。

这些只读检查不等于实际推理成功，不能验证 InvokeModel/Converse 的完整权限、运行时限流、响应或费用抵扣。实际调用按量计费，本次按用户偏好跳过。

## 尚未覆盖

- 正式 Agent 逻辑、实际模型推理、长任务/流式响应（当前代理适合短请求）
- 视频上传、数据解析、渲染和端到端处理
- GitHub 仓库授权及机器评分接口
- SageMaker GPU 创建
