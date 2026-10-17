# 从零运行一个回合

本地路线只需要 **Python 3.13、三个视觉模型、自己的 AWS Bedrock 权限**。不需要 S3、AgentCore 或 CloudFront；FFmpeg 随 Python 依赖安装。Node.js 22+ 仅用于前端测试和可选云部署。

## 1. 安装

在仓库根目录执行（macOS / Linux）：

```bash
python3.13 -m venv hidden-impact/.venv
source hidden-impact/.venv/bin/activate
python -m pip install -r hidden-impact/requirements.txt
cd hidden-impact
```

Windows 使用 Python 3.13，并通过 `.venv\Scripts\activate` 激活环境。后续 `python` 均指这个虚拟环境。

## 2. 准备视觉权重

从 [basketball_analysis 上游项目](https://github.com/abdullahtarek/basketball_analysis#-training-the-models)下载 `player_detector.pt`、`ball_detector_model.pt` 和 `court_keypoint_detector.pt`，放在自己选择的目录。HiAgent 使用其固定类别和关键点布局，不支持直接替换成任意 YOLO 权重。

在**单独的导出环境**安装导出工具，避免改变运行环境：

```bash
python3.13 -m venv .export-env
.export-env/bin/python -m pip install 'ultralytics==8.4.174' 'onnx>=1.17,<2' 'onnxruntime==1.30.0'
.export-env/bin/python scripts/setup_models.py \
  --player /path/to/player_detector.pt \
  --ball /path/to/ball_detector_model.pt \
  --court /path/to/court_keypoint_detector.pt
```

也可直接传入兼容的 `.onnx` 文件，此时运行环境即可执行安装命令，无需 Ultralytics。安装器检查输入 / 输出布局并保存校验值，最终应有 `models/basketball/{player,ball,court}.onnx`。模型约占 1 GB 磁盘，CPU 可推理；首次分析和渲染需要耐心等待。[来源及许可记录](../hidden-impact/models/basketball/SOURCES.txt)

## 3. 配置 Bedrock

安装 [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)，使用自己的账号配置 profile。例如已启用 IAM Identity Center 时：

```bash
aws configure sso --profile hiagent
aws sso login --profile hiagent
aws sts get-caller-identity --profile hiagent
```

也可使用标准 AWS 环境凭证或机器角色。这个身份需要在所选区域调用 `bedrock:InvokeModel`；默认模型为 `qwen.qwen3-vl-235b-a22b`，请先在自己的 Bedrock 账号确认模型可用及配额。`--region` 与 `--model` 可调整，但模型必须支持 Bedrock Converse 图像输入，并能满足现有 JSON 输出协议；其他模型需要自行验证。调用不是免费的。

## 4. 输入 → 成片

准备一段 **0.5–40 秒、单个进攻回合**的视频。可选配套 JSON 使用 `companion-v1/v2`：最小结构见 [`examples/companion.minimal.json`](../examples/companion.minimal.json)，完整结构见 [`examples/dallas/companion.json`](../examples/dallas/companion.json)。其中 `alignment.shotVideoTime` 是视频内出手秒数，`shotContext` 是对应出手记录，`roster` 是真实球员名单；缺失的指标应省略。

```bash
python scripts/analyze_video.py \
  --video /path/to/play.mp4 \
  --companion /path/to/companion.json \
  --profile hiagent --region us-east-1 \
  --out web/results/first-play
python server.py
```

打开 `http://127.0.0.1:8765/?result=results/first-play/showcase.json`，依次查看视频、故事线与数据。原视频对照也保存在输出目录。**本地网页的上传按钮连接云端 API**；本地计算请使用上述 CLI，在线上传需完成 [AWS 部署](aws.md)。

视觉检测按 6 fps 采样；默认 18 张全局上下文帧，Reviewer 另做局部角色核验。`--frames 20` 可调整全局采样，`--no-review` 可减少调用，但会省略独立复核。

| 输出 | 内容 |
| --- | --- |
| `replay.mp4` / `showcase.json` | 成片与前端展示入口 |
| `frame-*.jpg` / `presentation-plan.json` | 故事帧与渲染计划 |
| `analysis.json` / `result.json` | 原始分析与最终结果 |
| `review.json` / `references.json` / `review-report.json` | Reviewer 锚点、角色参考与调用记录 |
| `status.json` | 成功状态或具体失败原因 |

每次使用一个新的输出目录，避免覆盖旧结果。任务失败时会保留诊断文件；根据错误信息检查输入数据、模型权限与额度后重试。

## 5. 离线回放与重新渲染

查看随仓库提供的示例无需安装模型或登录：`python scripts/install_demo.py`，然后 `python server.py`。

已有最终 `result.json` 和对应原视频时，可不调用模型重新渲染：

```bash
python scripts/analyze_video.py --video /path/to/play.mp4 \
  --analysis /path/to/result.json --out web/results/rerender
```

输入必须包含完整呈现数据或足够的已核验证据，不能只传 `showcase.json`。支持使用复核后的呈现计划。
