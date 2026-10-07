# Hidden Impact / NBA Courtvision

NBA 单回合视频的幕后贡献分析原型：篮球专用视觉模型、连续动作评分、Qwen VLM 核验、三角色视频叠层和关键帧时间轴。

- [主项目与实现说明](hidden-impact/README.md)
- **[AWS 清理后的完整恢复步骤](hidden-impact/docs/RESTORE.md)**
- [模型来源](hidden-impact/models/basketball/SOURCES.txt)

本机入口：`cd hidden-impact && .venv/bin/python server.py --port 8765`。
完整云功能需要赛事 AWS 开放登录；本地前端文件和离线回归测试不依赖 AWS 存续。

所有云资源只部署 `us-east-1`；主办方已初始化 CDK，**不要执行 `cdk bootstrap`**。
凭证、团队访问码、模型权重、原始视频和私有云快照不纳入 Git；保留本机 `backups/` 以恢复云端数据。

当前为研究原型：人物关联、VLM 持球理解和贡献归因仍有误差，不能将工程分数当作经过验证的实际贡献。
