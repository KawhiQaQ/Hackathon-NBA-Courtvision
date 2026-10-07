# Hidden Impact · NBA 视频战术工作台

> **最新状态（2026-10-08）**：请优先阅读 [AWS 清理后恢复说明](docs/RESTORE.md)。本文后半部分保留了历次迭代记录，旧版模型、阈值及界面描述不代表当前实现。

当前是 `temporal-impact-v5` + `focused-outcome-v2`：篮球专用检测、连续窗口评分、最终出手与举球释放冲突核验；界面使用固定角色「主角 / 收益队友 / 防守者」及三帧时间轴，已去掉小球场曲线和独立总结。60 项 Python 回归及前端回归可以从仓库内 fixtures 离线运行。

当前主数据源已经改为 **NBA 中国官网 Inside the Game**。SkillCorner 仅作为此前的数据实验保留，不参与当前视频分析，主页面也不再展示它。

## 打开应用

- 本机：<http://127.0.0.1:8765>
- AWS：<https://d18o4ltbbhvywp.cloudfront.net>

```sh
cd '/Users/kawhi/Documents/AI+NBA/hidden-impact'
python3 server.py --port 8765
```

本机服务使用 `.cloud-config.json` 与 `.team-access-code` 在服务器端代理云端请求，不向网页泄露 AWS 凭证。云端网页需要团队访问码，存于本机被 Git 忽略的 `.team-access-code` 文件。不是个人模型 API Key。

## 数据来源

官网：<https://china.nba.cn/inside-the-game>。仅对公开页面正常使用的接口做小规模读取、缓存，不绕过登录或访问限制。

`scripts/build_nba_samples.py` 获取 7 段官方出手视频，并用 `gameId + eventId` 对齐逐次出手记录。样本来自 `0042500404`，包含官方提供的出手人、节次、比赛时钟、出手方式、结果、预期命中率。

球员 Gravity 来自 `2025–26 / Playoffs` 汇总榜：总体、持球/无球、外线/内线引力。**这些是该阶段的球员汇总指标，不是某个回合的瞬时引力**，仅在身份可匹配时作背景显示，不参与回合评分。没有逐帧 tracking，没有伪造精确防守距离、移动轨迹或瞬时 Gravity。

当前样本偏向官网精选进球，存在选择偏差，不能用来评估整场贡献分布。视频及数据权利仍归原权利方；SkillCorner 的 MIT 许可不覆盖 NBA 视频。正式参赛素材以主办方授权范围为准。

## 当前交互与视觉分析（2026-10-07）

默认进入空白工作台：导入素材 → 分析视频 → 核验与导出。公开示例只在主动选择后加入项目，旧浏览器结果不自动加载；历史项目需主动打开。支持私有视频上传、可选JSON配套数据、项目内批量分析、候选排序和结果导出。当前输入是0.5–40秒单回合片段，不宣称全场自动切分已经完成。

混合管线：S3视频6fps采样＋浏览器18张精确锚点 → AWS Lambda上的YOLOX-S人物检测 → 颜色/重叠/位移的保守短时关联 → 带临时编号的关键帧 → AgentCore中的Qwen3-VL角色与动作候选 → 程序空间评分。YOLOX是预训练神经网络；关联算法是启发式，不是新的训练模型。位置框完全取自检测器，禁止使用VLM编造的框。画面中的裁判/观众可能被检测，人物编号不是球员姓名；模型性能没有得到比赛标注集验证。

人物框可以在相邻可靠观测之间插值，虚线仅表示近期画面轨迹。切镜、超过1.3秒间隔或低关联置信不连线。没有球场标定，不显示米数、速度或真实战术控制面积。

### 评分 v2.2：空间机会候选指数

研究依据：

- [Cervone 等，JASA 2016，EPV](https://arxiv.org/abs/1408.0777)：借鉴动作前后比较机会价值的视角。该论文通过完整光学tracking和训练后的概率过程模型估计回合预期得分。当前代码**没有复现EPV**。
- [Wu 等，IEEE TVCG 2023，OBTracker](https://dengdazhen.github.io/assets/pdfs/obtracker.pdf)：借鉴位置优势、队友协作、时间序列与可解释展示。原文以切入者为主要对象，并指出掩护者贡献仍是局限，不能据此宣称我们的掩护者归因已获验证。
- [McIntyre 等，Sloan，Ball Screen Defense](https://www.sloansportsconference.com/research-papers/recognizing-and-analyzing-ball-screen-defense-in-the-nba)：参考对防守反应的情境区分；靠近不能自动判为成功掩护。当前没有训练该文中的防守分类器。

计算实现为 `cloud/agent/impact_score.py`。VLM只能选择贡献者A、受益者B、防守者D，程序从检测轨迹取几何数据。至少3个共同观测、同镜头、可见覆盖≥75%，相邻间隔≤1.3秒，明显缩放或关联质量不足时放弃评分。

1. 足部中点转为统一图像比例坐标，三者平均人物高度作为距离归一化尺度。
2. `g = 结束附近B-D间距中位数 - 开始附近B-D间距中位数`；`R=clip(g/1.5,0,1)`。
3. 掩护几何项：A-D邻近程度×A到D-B线段的邻近程度；牵制项：A-D保持邻近程度×摆脱改善。这只是几何兼容性，不能证明防守人心理注意力或身体接触。
4. `P`为超过基线0.25人物高度的间距优势持续时间占比。无正向改善时掩护／牵制和持续项也不给分。
5. 前后各采用最多0.5秒的窗口中位数。原始指数 `40R+35(IR)+25(PR)`；质量 `Q=可见覆盖×最弱角色检测置信均值×轨迹关联置信均值`；最终候选指数为原始指数×Q。质量低于0.3不评分。权重、阈值均为**待标注集校准的工程选择**，不是论文测得的系数；这是图像代理量，不是因果贡献，不跨不同视角作精确比较。

命中结果、赛季Gravity、VLM自报高置信均不能直接加分。配套JSON若给出同视频时间序列expectedPoints，独立显示动作前后变化，不把它归因给某个人，也不改变上述分数。

### 配套数据合同

```json
{"schema":"hidden-impact/companion-v1","source":"数据提供方","opportunity":[],"notes":"可选说明"}
```

`opportunity` 可包含 `{"time":1.0,"expectedPoints":0.8}` 形式的真实记录：time是当前视频内秒数，必须递增且不越界；expectedPoints范围0–4。空数组表示未提供。该数据按视频绑定，标为用户提供；不覆盖服务器保存的官方出手清单。正式赛事字段仍需适配。

### 部署专用视觉网络

`.venv/bin/python scripts/prepare_vision.py` 构建Python3.13/ARM64 Lambda layer。使用官方YOLOX-S ONNX权重（Apache-2.0，许可在layer中保留），SHA256在脚本中校验；ONNX Runtime、NumPy、Pillow版本固定。CPU推理运行于2GB内存工作Lambda，无需GPU实例。然后执行原有 `scripts/deploy.py`。

`tests/test_hybrid.py`验证公共平移/缩放不凭空改变相对量、静态站位不获得改善分、断镜/弱关联放弃评分、VLM坐标不进入标注、外部预期分不污染归因分。真实云调用使用 `scripts/verify_hybrid.py`，会产生模型调用费用。

## 早期版本功能记录

- 视频播放、按候选证据指数排序和比赛时间排序、单条/批量分析。
- 从单回合视频均匀抽取 18 张 JPEG 关键帧，使用真实 AWS Bedrock Qwen3-VL 235B A22B。
- CloudFront → API Gateway → Lambda → AgentCore Runtime → Bedrock，异步任务和状态查询，页面刷新可恢复正在处理的任务。
- 官方逐次出手数据在服务器端从已核验的 S3 清单加载，避免由网页伪造样本配套数据。
- 无球候选、结构化证据、程序计算的证据支持指数、可点击关键帧及暂停画面的人物框、贡献片段回放、中文解说与浏览器朗读。
- 私有 S3 视频库、临时播放链接、上传 40 秒以内的单回合视频、结果 JSON 和文字导出。
- 无证据时返回空结果；低置信事件不评分；最终出手者不能被重复计为幕后贡献者。

## 已停用的 v1 指数（仅供旧记录解释）

掩护证据 30、防守响应 30、空间变化 25、受益机会 15。分值由程序根据模型提供的有效观察引用计算；防守响应和空间变化至少要引用两个不同时间点。掩护项还需要观察文本包含掩护语义。无效时间点、画面外框、出手者候选会被剔除。

这是**视频证据支持指数**，不是经过验证的因果影响力或真实得分贡献。模型的事件判断和人物定位仍需人工回放核验；汇总 Gravity 与命中结果不参与计分。抽帧不能保证还原全部短暂动作。

## 云资源

CDK 栈 `HiddenImpactTeam14`，赛事账号 `214299441669`，仅 `us-east-1`。单独保留原有 `NbaTeam14Preflight` 连通性栈。

- AgentCore：`nba_team14_hidden_impact-hvcQW754wh`
- CloudFront：`E30YXSOB5NJYAG`
- 模型：`qwen.qwen3-vl-235b-a22b`
- 模型调用与上传接口需要团队访问码；API 限速、工作 Lambda 并发为 2。
- 任务文件保存 30 天；视频存储桶保留。SSO 凭证不进入网页。无 GPU、EC2 或 NAT Gateway；YOLOX 在工作 Lambda 内进行 CPU 推理。
- 按赛事账号实际用量计费，是否被赛事额度抵扣由主办方确定。

```sh
# 主办方已 bootstrap，绝对不要执行 cdk bootstrap。
~/.local/bin/aws sso login --profile nba-sso
.venv/bin/python scripts/deploy.py
.venv/bin/python scripts/publish_nba.py
```

`infra/cdk.json` 已带 `NBAHackathonParticipantBoundary`。CDK 复用相邻 `aws-preflight/node_modules` 中锁定的工具版本。首次准备 Python：使用 Python 3.12+ 创建 `.venv` 并安装 boto3、imageio-ffmpeg、pillow；AgentCore 的纯 Python boto3 依赖通过 `pip install --target cloud/agent/vendor boto3` 打包。

## 检查

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js
# 下面会真实调用付费云端模型，按需执行：
.venv/bin/python scripts/verify_hybrid.py
```

测试覆盖：数据/视频配对、时间点合法性、无效定位框过滤、低置信放弃评分、出手人排除、Gravity 不影响回合分数等。云端实测记录保存在被 Git 忽略的 `verification/`，前端样例分析来自真实模型响应；已发现的球员身份误判按任务 ID 撤下，原始响应保留在验证目录和 S3。候选结果均明确标为尚未人工核验，不能把模型自报的高置信度当作事实正确率。

## 逐人分析 v3（2026-10-07）

入口仍为空白，导入视频后主动开始分析。新链路先把 YOLOX 人物候选裁剪成逐格接触表，由独立 VLM 调用筛选球员，再交给逐人 VLM 核对身份、攻防角色与持球状态；输出只保留有精确检测引用支持的球员。VLM 给球员分配 P 编号，可在多个短轨迹 T 编号之间关联；从当前视频中核验的球员躯干颜色学习两队配色原型；颜色可分时拒绝明显跨队的身份跳变，不硬编码球队主色。赛事预期为独行侠与火箭，当前验证为尼克斯与马刺；不同球衣版本仍须逐段校准。身份只在核验锚点周围 0.8 秒内传播，切镜与身份冲突不外推。未识别者不会被凑成十人，也不能保证分类全对。

每个被识别的球员都有报告、可见时间、观察摘要和可点击证据。程序逐个检查无球队员与队友/防守者的几何时间窗，而不再要求 VLM 先输出符合三帧硬门槛的罕见事件。贡献候选同时需要靠近相关防守路径和受益者间距增加；持球时间窗排除。动态几何占 80 分（32/28/20），另有持续无球空间支撑 20 分，各自乘证据质量，是未经标定的空间协同代理量。空间支撑要求无球队员附近有防守人，并与可确认持球者保持较远画面距离至少0.5秒；它是位置结构而非防守吸引力。充分观察而无信号时显示 0（不是实际贡献为零）；证据不足显示原因；防守方不计进攻贡献分。

界面包括逐人卡片、选中人物高亮、脚下标记、近期移动箭头、近邻虚线、三角色关系区域、画面位置示意图、动作前后证据帧和一键跳转。关系区域不是防守覆盖范围，示意图不是实际球场坐标。历史项目支持导入导出的逐人分析 JSON，云端视频过期或属于另一团队时不能恢复播放。

## v3 真实验证记录

2026-10-07：完整异步 AWS 调用首先返回8名球员，但人工检查发现包含裁判/场边人员，因此该结果不可作为成功质量验证。新增独立裁剪分类后，同一13秒示例通过真实 AgentCore→Bedrock 两次模型调用返回6份球员观察。随后用同一次模型引用和真实检测颜色做确定性重算，拒绝31条跨队颜色不一致的定位，产生一项5分空间支撑候选。抽查0.10s与4.67s画面，先前误收的裁判/场边人员已排除；尚未达到完整十人覆盖，有一份报告证据极少，身份与分数都需要继续核验。

验证文件 `verification/roster-reviewed-export.json` 可通过“历史项目→导入分析文件”打开。它是实际云端模型结果加本地确定性颜色/评分重算，非人工编造数据。39项Python测试通过；`node tests/test_web_render.cjs` 使用该真实结果验证所有逐人报告、证据链接和空间叠层的渲染逻辑。浏览器自动化连接中断，最终点击和截图验证未完成，不能将DOM模拟测试称为浏览器测试。

AgentCore改为监听就绪后按需初始化模型客户端，分析时健康检查返回HealthyBusy，避免长任务被认作空闲。独立请求与后续真实模型调用已成功。

## 当前质量验证

2026-10-07：v2.2 在浏览器中完成公开示例和私有上传两条真实 AWS 分析流程，分别生成 78 / 96 个检测时刻，每段均提供 18 张 VLM 关键帧与可重新读取的云端缩略图。两段均未产出可评分候选，因此只确认混合管线可运行，不将此视为识别准确率提高的证据。刷新后空白入口、主动打开历史项目、视频关键帧跳转和人物叠层已验证。导出按钮的浏览器自动化下载事件超时，文件落盘尚未验证。

7 段官网视频已经实际通过云端模型链路。初次测试中4段没有产生可评分事件，另3段的候选因身份或动作描述错误被画面复核撤下。这说明云端调用和数据配对可用，但自动归因尚未达到可靠水平；不能把这组样本当成准确率证明。下一步需要建立包含正例、负例的小规模人工标注集，核对出手前动作、球员身份和标注框，再校准自动筛选。原版规则测试19项通过；v2加入空间评分和配套数据测试后共29项通过。

## 尚需正式比赛数据验证

完整比赛的自动回合切分、赛事逐回合 Gravity/位置数据适配、视频时钟精确同步及比赛要求的提交协议。当前上传流程支持已经切好的单回合视频，不能将它称作全场自动分析完成版。

## Continuous video pipeline (2026-10-07)

The current `temporal-impact-v5` implementation is in `cloud/api/court_vision.py`,
`cloud/agent/temporal.py`, and `cloud/api/render_video.py` (agent modules are mirrored
into the API bundle). It uses basketball-specific player/referee, ball, and 18-landmark
court models, velocity prediction with global assignment, current-video jersey appearance,
and Qwen verification of multi-time body crops. Model provenance is in
`models/basketball/SOURCES.txt`; large weights are private S3 objects, downloaded into
Lambda ephemeral storage rather than the dependency layer.

Scoring scans continuous off-ball hypotheses. Unknown possession may generate an internal geometry proposal, but final publication requires a focused visual check. Screen candidates require an intervening
position on the defender–beneficiary path, subsequent separation improvement, and
improvement against the beneficiary's nearest defender. Decoy candidates additionally
require court-calibrated actor/defender motion in a consistent direction. Sustained
spacing is a separate, lower-budget descriptive component. Confidence is displayed
separately from magnitude; the 35/25/20/20 weights are engineering choices, not validated
EPV or causal player credit. Tracking interruptions, possession ambiguity, cuts and
unknown jersey identity limit attribution. A real zero remains possible when observable
windows contain no accepted contribution signal.

Official shot game clocks can be aligned with VLM-read scoreboard crops using a robust
video-time/clock offset. This clips attribution to the original attack instead of
crediting post-shot recovery. The recorded uncertainty is ±0.85 seconds. Aggregated
season Gravity is context only. `hidden-impact/companion-v2` accepts explicit player-ID
mapping, normalized court tracking, ball handlers, per-time attention share, and expected
points; no per-possession series is invented from aggregate statistics. Supplied tracking
can replace estimated score coordinates while image boxes remain detector-grounded.

The workbench now renders fading, camera-projected focus trails, relevant defender
movement, a synchronized court view, and a clickable separation timeline. Slow playback
and a private downloadable 24fps H.264/AAC tactical MP4 are supported. The export includes
an external lower strip with measurement timeline so analysis does not obscure the game.

Validation: `python -m unittest discover -s tests -p 'test_*.py'` and
`node tests/test_web_render.cjs`. Real clips, scoring outputs, render screenshots and
cloud deployment evidence are under `verification/temporal-*` and `verification/motion-*`.
Use `scripts/verify_temporal_cloud.py` for a real paid AWS run. This is a research prototype:
identity switches and VLM possession errors remain possible, and candidate accuracy has
not been benchmarked against coach-labeled ground truth. Reference ideas: OBTracker
(https://dengdazhen.github.io/assets/pdfs/obtracker.pdf), Omnioculars
(https://arxiv.org/abs/2209.00202), and basketball_analysis
(https://github.com/abdullahtarek/basketball_analysis).


Focused verification (`candidate_review.py`) marks actor A and teammate B on three source
frames. Confirmed on-ball actors update the possession interval and trigger deterministic
rescoring; spacing support also requires B to be visually confirmed as a ball handler.
An explicitly inconsistent identity is rejected. Where visual identity is uncertain,
continuous tracking plus temporally sampled jersey checks and measurement quality >=0.65
can support a temporary track candidate, labeled `continuous-track-and-jersey`; this is
not a confirmed person identity. Unverified proposals are removed from the candidate
ranking, and insufficient possession coverage is not published as zero contribution.
Private content-addressed perception caches include model revision, video object ETag,
and exact source anchor hashes. Cached CV output does not bypass fresh candidate checks.
