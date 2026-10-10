# Team 14 · HI | Hidden Impact

让深度数据回到比赛画面，从“做了什么”和“为什么能形成威胁”两个角度解读幕后 MVP。

## 观看与使用

[作品页](https://d2pfr8ulgem4g5.cloudfront.net/)直接展示已生成的成片，无需上传或等待分析。

- **战术回放**：固定角色标牌、双色方向箭头、战术板与深度数据比较；关键时刻定格并展示分阶段解说。支持切换原视频。
- **故事线**：带可视化标注的关键帧，逐段说明幕后 MVP、受益队友与防守者之间的配合。
- **数据分析**：回合贡献、机会质量与球员背景数据；多个同场回合可汇总排名。
- **导入分析**：`workbench.html` 支持视频及配套 JSON 上传，异步查询任务状态并打开完整结果页。

## 系统链路

S3 素材 → 篮球视觉检测与短时人物关联 → Bedrock AgentCore / Qwen3-VL → 候选核验与贡献评分 → 分阶段解说 → FFmpeg/Pillow 合成 → S3 / CloudFront 发布。

视觉模型提供人物与球的位置证据；VLM 结合关键帧、角色候选和深度数据解释动作并生成解说。通用渲染器将结构化结果转换为 MP4 和故事帧。系统另有发布前角色与故事编辑接口，编辑成片与原始分析分别保存。

## 数据口径

- 官方出手记录按比赛、球员和事件对应；预期命中率与同场同球员同类出手均值比较，差值以百分点表示。
- 球员引力及创造机会等阶段指标用于解释背景威胁；此前命中情况仅采用当前事件之前的数据。
- 统计差值不等于某位球员造成的因果增益。贡献分是基于动作证据与机会质量的工程观察指数。
- 画面位置来自视觉分析，不是官方逐帧 tracking。未能核验角色时保留数据解读，不授予确定的 MVP。
- 多回合汇总的范围是导入的回合集合；同一回合去重，身份不确定的回合不合并到球员排名。

素材来源保存在结果的 publication 信息中。NBA 深度数据来源为 [NBA China 深度赛场](https://china.nba.cn/inside-the-game)；公开发布使用主办方提供或已获授权的视频。视觉模型来源见 [SOURCES](models/basketball/SOURCES.txt)，字体许可见 [OFL](cloud/api/fonts/OFL.txt)。

## API

除健康检查外，下列业务接口使用 `X-Team-Key`。公开作品页观看不需要访问码。

| 接口 | 用途 |
| --- | --- |
| `GET /api/health` | 健康检查 |
| `POST /api/upload`、`POST /api/upload/complete` | 获取 S3 上传表单并确认素材 |
| `POST /api/jobs` | 创建视频分析任务 |
| `GET /api/jobs/{id}` | 获取状态、分析结果和媒体地址 |
| `POST /api/games`、`GET /api/games/{id}` | 创建、读取同场回合汇总 |
| `POST /api/presentations` | 根据已有任务与角色、故事编辑数据生成独立成片 |

视频任务接受 `{mode:"video",video:{id,title,duration},frames:[{time,image}],companion?:...}`；image 为 JPEG base64，3–20 帧。配套出手数据示例见 [shot-context-example.json](web/data/shot-context-example.json)。

分阶段解说使用 `hidden-impact/timed-narration-v1`，每段包含 `start/end/title/text/frameTimes`。展示结果使用 `hidden-impact/showcase-v1`，包含角色、证据帧、运动提示、数据图表和视频资源。AgentCore 入口为 `POST /invocations`，健康检查为 `GET /ping`。

## 开发与发布

环境准备、模型资产恢复、CDK 和测试命令见 [开发与部署](docs/RESTORE.md)。这些是项目维护说明，不额外规定比赛提交材料。

在已配置的开发环境中：

```sh
cd hidden-impact
.venv/bin/python server.py --port 8765
```

本地导出单回合结果：

```sh
.venv/bin/python scripts/export_result.py --analysis result.json --video input.mp4 --out web/results/my-play
```

访问 `/?result=results/my-play/showcase.json`。云端已完成任务使用 `scripts/publish_result.py --job <任务ID>` 发布；该脚本更新本队网站，不提交赛事表单。

## 代码结构

| 目录 | 内容 |
| --- | --- |
| `cloud/api/` | HTTP API、任务执行、视觉处理、评分、渲染 |
| `cloud/agent/` | AgentCore、模型调用与解说 |
| `infra/` | CDK 基础设施 |
| `web/` | 作品页、工作台、故事线与数据展示 |
| `scripts/` | 素材导入、部署、导出与发布 |
| `tests/` | API、评分、渲染及前端回归测试 |
| `models/basketball/` | 模型来源、版本与哈希清单 |
