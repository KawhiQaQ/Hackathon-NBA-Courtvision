# Hidden Impact · Team 14

视频 → 篮球视觉检测 → AgentCore / Qwen3-VL → 贡献候选核验 → 深度数据与 AI 解说叠加 → 成片与关键帧。默认作品页直接呈现已经生成的结果；`workbench.html` 是重新分析入口。

## 当前运行与部署（2026-10-10）

Python 3.12+、Node.js/npm、AWS CLI v2。所有云端资源在本队账号 `us-east-1`；只使用主办方配置的 SSO profile，**不要运行 `cdk bootstrap`**。账号 ID 从 STS 读取，不再回退到旧账号。

从仓库根目录：

```sh
npm ci --prefix aws-preflight
python3 -m venv hidden-impact/.venv
hidden-impact/.venv/bin/python -m pip install -r hidden-impact/requirements.txt
hidden-impact/.venv/bin/python -m pip install --target hidden-impact/cloud/agent/vendor -r hidden-impact/cloud/agent/requirements.txt
hidden-impact/.venv/bin/python hidden-impact/scripts/prepare_vision.py
```

模型大文件保存在本队私有 MediaBucket，来源与固定哈希见 `models/basketball/SOURCES.txt` 和 `manifest.json`。新机器通过 `scripts/restore_models.py --bucket <本队MediaBucket>` 恢复并校验；桶已被销毁时从本地私有备份恢复，不能假设 Git 包含权重。

```sh
cd hidden-impact
aws sts get-caller-identity --profile nba --region us-east-1
.venv/bin/python scripts/deploy.py
.venv/bin/python -m unittest discover -s tests
node tests/test_web_render.cjs
node tests/test_game_view.cjs
node tests/test_generated_showcase.cjs
node tests/test_showcase_insights.cjs
```

最新地址取自 `infra/cdk-outputs.json` 的 `FrontendUrl`，不复用旧 CloudFront 地址。部署自动上传模型；团队访问码保存在 `.team-access-code`，不提交仓库。详细备份说明见 [RESTORE](docs/RESTORE.md)。

## 官方片段与真实推理

`scripts/ingest_official.py` 接受主办方视频、明确核对过的比赛/出手者/事件 ID，读取 NBA 深度数据，将素材登记至本队私有 S3，并提取普通任务请求。它不预置候选主角或解说。示例（练习片段）：

```sh
.venv/bin/python scripts/ingest_official.py --video data/videos/official/dallas-practice.mp4 --id dallas-practice --game 0022500701 --player 1642843 --event 666 --source https://comfile.csdnimg.cn/file/train_video.zip --shot-time 17.3 --out data/frames/official/dallas-request.json
.venv/bin/python scripts/smoke_release.py --api-only --request data/frames/official/dallas-request.json
.venv/bin/python scripts/publish_result.py --job <成功任务ID>
.venv/bin/python scripts/smoke_release.py --public-only
```

真实任务经 CloudFront → API → Lambda → AgentCore → Bedrock → 渲染与 S3；smoke 脚本保存原始任务回执于私有 `verification/`。`--shot-time` 是视频内出手对齐秒数，提供时记录其复核来源；不提供则只显示回合数据摘要，不伪装实时数据。网页上传也可附配套 JSON，见 `web/data/shot-context-example.json`。

未能核验出幕后 MVP 时，真实出手数据和分段解说仍可形成数据解读视频，主角及分数保持未确定。该状态不得计入 MVP 排名。视觉模型与 VLM 仍可能认错人，跑通管线不等于归因准确。

公开发布只复制来源明确的已完成任务，并保留生成/复核记录；媒体是持久化对象而非临时签名 URL。CDK 不上传本地 `demo/`、`media/`、`posters/` 等研究素材。`/readme` 展示素材来源、AI 解说声明与接口。发布脚本不会自动填写比赛提交表单；考试视频发布后需以同样链路生成、检查并更新正式结果。

## API

- `GET /api/health`：公开健康检查。
- `POST /api/upload` → S3 表单上传 → `POST /api/upload/complete`：私有素材导入。
- `POST /api/jobs`：`{mode:"video",video:{id,title,duration},frames:[{time,image}],companion?:...}`；`image` 为 JPEG base64，3–20 帧。返回任务 ID。
- `GET /api/jobs/{id}`：排队/运行/失败/完成状态，完成结果包含模型用量、证据、分阶段解说、presentation 与签名媒体地址。
- `POST /api/games`：同场已核验任务汇总；`GET /api/games/{id}` 返回汇总结果。

除健康检查外请求头为 `X-Team-Key`。AgentCore 标准入口为 `POST /invocations`，接受相同视频与关键帧合同及 worker 计算的视觉证据；`GET /ping` 用于 runtime 健康检查。没有额外私有评分协议的假设。

## 历史研究记录

以下保留早期设计与样本来源，旧模型/阈值/部署描述不替代上面的当前运行步骤。

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

### 普通分析结果与展示页接口

当前生产路径：视觉检测/跟踪 → 时序候选评分 → VLM 核验角色与出手 → `narrate-video` 分段解说 → `presentation.build` → 视频及胶卷帧渲染。除无球掩护、跑位、空间支撑外，`draw-kick` 候选通过持续球权转移、相关防守者靠近和接应空间计算；必须再核验传球、相关防守响应与队友最终出手，才进入排名。

- `result.narration` 使用 `hidden-impact/timed-narration-v1`，每段有 `start/end/title/text/frameTimes`。实际生成器在 AgentCore 调用 Bedrock `converse`，输入原视频 JPEG 帧、已核验角色和可选深度数据。失败返回 unavailable，不替换成示例文案。
- `result.presentation` 使用 `hidden-impact/showcase-v1`，生产结果 `mode=analysis`。角色、评分、故事帧、解说和可用数据图表来自本次分析。`presentationMotion` 提供三人位置、同镜头短缺帧插值和主角后续移动方向。长时间缺失或断镜时保留身份状态，不捏造位置/方向。
- Worker 导出完整片段 MP4 和已标注 JPG，完成后工作台可“打开完整结果页”。`/?job=<job>` 使用团队会话获取有时效的签名资源；适合团队查看。正式提交可使用静态结果包，避免依赖评审登录和资源签名有效期。
- 本地生成静态结果包：`.venv/bin/python scripts/export_result.py --analysis result.json --video input.mp4 --out web/results/my-play`；然后打开 `/?result=results/my-play/showcase.json`。将生成目录放入现有网站部署资源，即可复用同一展示页。没有合格事件时不导出虚构 MVP。
- 不同视频无需修改展示页中的人物、球队或时间点。官方出手记录只用于对应视频；同场对照均值需要匹配的完整 `playerShots`，缺失时省略。Gravity 保留阶段汇总范围，不当成本回合实时归因。

验证：`test_worker_presentation.py` 使用内存 AWS/Agent 双替身与真实视频编码验证任务链；`test_presentation.py` 覆盖评分核验、断镜缺帧、数据匹配和渲染；`test_generated_showcase.cjs` 覆盖通用展示页入口。测试替身不能证明云端权限或真实模型效果；恢复 AWS 后仍需执行真实视频调用验收。

渲染字体随 API 部署包提供：Google Fonts 的 Noto Sans SC，SIL Open Font License；许可保留于 `cloud/api/fonts/OFL.txt`。下载来源为 `https://github.com/google/fonts/tree/main/ofl/notosanssc`。

### 展示角色与故事校对

`POST /api/presentations` 使用相同的团队认证，接收 `sourceJob` 与 `review`，
从已完成任务派生独立的展示任务。原模型事件、评分和解说保持可追溯；
校对版存储 `presentationReview`、`originalNarration`，并标记 `reviewed-story`，
不计入自动幕后 MVP 排名，也不把校对文案声称为未经编辑的模型输出。

校对 JSON 示例为 `data/reference/dallas-presentation-review.json`：固定主角、
受益队友、防守者三人；位置格式为 `[秒, 640宽画面的脚底x, 360高画面的脚底y, 人物高度]`；
切镜或画外使用三个 `null`。输入必须绑定原视频 ID 和 SHA-256，覆盖全片，
故事段落连续且包含可跳转的 `seek`。相同的渲染器输出带标签、双色方向箭头、
柔和聚焦、数据卡与分段解读的视频及胶卷帧。方向提示是图像空间的后续移动，
不是场地坐标轨迹复原或引力的因果估计。

```sh
.venv/bin/python scripts/submit_presentation.py --source-job <已完成任务ID> --review data/reference/dallas-presentation-review.json
.venv/bin/python scripts/smoke_release.py --api-only --job <返回的新任务ID>
.venv/bin/python scripts/publish_result.py --job <返回的新任务ID>
```

以上只操作本队作品资源，不提交或修改赛事评分系统。原始模型分析接口
`POST /api/jobs` 继续使用自动检测、候选核验、评分与实际模型解说。

成片渲染读取源视频的真实尺寸，保留最高 1920×1080 的比赛画面，不将低分辨率
素材强行放大。信息条放在画面外侧，因此横屏 1080p 素材的完整成片为
1920×1368。字体、标签和箭头在目标尺寸直接绘制；H.264 使用 CRF 17 / fast，
关键帧 JPEG 使用质量 95、无色度降采样。当前回放帧率沿用展示时间线的 24 fps。

视频内深度数据使用双条比较：预期命中率固定 0–100% 刻度，显示同场、同球员、
同类出手的均值与本次出手，以及直接由两值相减计算的百分点差；该均值包含本次
出手。引力使用共享零点的有符号条形图，对比球员阶段画像与队内中位数。
缺失基准时不生成差值。历史均值不等于主角介入前的状态，差值不作为主角的因果
贡献分；战术作用仍由同步视频证据解释。卡片固定位置，得分结果只在对齐的出手
时刻之后揭示；详细来源和样本口径保留在分析结果与页面数据区。

引力细分项通过 `gravityContexts` 按球员 NBA ID 和视频时间窗绑定，不再默认
使用出手者的无球外线引力。独行侠练习片段的 0–12.3 秒绑定弗拉格的持球外线
引力，之后切入出手质量对比；没有确认上下文时仅展示总体阶段画像，细分指标
缺失时不拿其他指标替换。该配置只选择官方数据字段，不修改其数值。

主角背景数据可通过 `scripts/enrich_actor.py --video <id> --player <NBA-ID>
--game <game-id> --upload` 从公开 NBA 接口补充到本队视频素材库。原分析任务保留
不变；新的展示任务从素材库读取 `playerProfiles`，并按主角的已确认 NBA ID 关联。
当前独行侠版本用加福德的创造机会/投篮得分影响力解释贡献构成，用本场当前事件
之前的两分出手说明终结威胁，最后切入弗拉格的出手机会。两个影响力组成项不是
前后提升；阶段画像和先前出手也不被折算成该回合的因果分数。无匹配身份/比赛或
缺失数据时不替换成队友数据。来源、取数时间和原始字段存入独立参考文件。
