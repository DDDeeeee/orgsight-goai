# OrgSight

OrgSight 是面向管理者的多 Agent 组织洞察 Demo，基于合成组织数据回答人员岗位适配、协作优势和组织风险等问题。项目参加 GOAI 世界人工智能开源大赛 Agent Infra 赛道。

用户在管理页面输入自然语言问题并选择分析团队后，请求会直接进入对应的 AgentTeams Team Leader。Leader 负责创建任务、委派专业 Worker 和验收结果；Worker 通过只读 MCP 工具访问授权范围内的组织数据，最终生成结构化 Markdown 分析报告。

## 已验证能力

当前完成端到端验证的是“人才与角色洞察”团队的岗位分析链路：

```text
管理页面
  -> talent-role-insight-lead
  -> role-and-position-analysis-worker
  -> OrgSight MCP
  -> PostgreSQL 合成组织数据
  -> result.md
  -> 已完成案例页面
```

岗位分析报告包含分析范围、结论摘要、关键判断、详细分析、协作影响、风险与成立条件、依据、信息缺口和置信度。

仓库中还包含协作治理、业务运营和管理决策模拟等团队的 Agent 与 Skill 设计骨架。这些扩展团队尚未完成端到端验证，不属于当前可运行 Demo 的验收范围。

## 演示数据

当前 Demo 使用完全合成的组织基线：

- 22 名合成人员；
- 6 个正式组织单元；
- 正式岗位和汇报关系；
- 人物事实档案与人物职业模型；
- 无方向协作关系快照；
- 不包含真实企业数据、真实员工信息或生产配置。

结构化 fixture 位于 `fixtures/demo-office/`。人物模型通过初始化脚本写入 PostgreSQL，并生成可读的 Markdown 文档至 `data/model-documents/`。

## 项目结构

```text
agent-specs/              Agent、Team 和 AgentTeams package 定义
contracts/                数据与输出契约
data/model-documents/     生成后的人物模型 Markdown
fixtures/demo-office/     合成组织、人物和关系数据
migrations/               PostgreSQL 数据库结构
scripts/                  数据导入与模型文档生成脚本
skills/                   OrgSight 领域 Skills 与参考资料
src/orgsight/             MCP、授权、数据访问和管理页面
tests/                    自动化测试
```

## 与 AgentTeams 的关系

OrgSight 与 AgentTeams 是两个独立仓库：

- 本仓库负责业务数据、Agent/Skill 定义、只读 MCP、授权逻辑和展示页面；
- [AgentTeams](https://github.com/DDDeeeee/AgentTeams) fork 负责 Manager、Team Leader、Worker、Task、Room、Matrix 通信和运行生命周期。

本仓库不复制或嵌入 AgentTeams 源码。运行完整 Demo 时，需要单独部署对应版本的 AgentTeams fork，并安装 `agent-specs/packages/` 中的 Agent package。

## 环境要求

- Python 3.11+
- PostgreSQL
- Docker
- AgentTeams embedded runtime
- 支持 OpenAI 兼容接口的模型服务

## 本地初始化

创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

复制环境变量模板：

```bash
cp .env.example .env
```

`.env` 只用于本地运行，已被 Git 忽略。请勿将 API Key、数据库密码、Matrix 密码或其他运行凭证提交到仓库。

初始化独立 Demo 数据库：

```bash
createdb orgsight_demo
psql postgresql://localhost/orgsight_demo --set ON_ERROR_STOP=1 --file migrations/versions/0001_demo_organization.sql
psql postgresql://localhost/orgsight_demo --set ON_ERROR_STOP=1 --file migrations/versions/0002_skill_result_storage.sql
psql postgresql://localhost/orgsight_demo --set ON_ERROR_STOP=1 --file migrations/versions/0003_mcp_task_authorization.sql
psql postgresql://localhost/orgsight_demo --set ON_ERROR_STOP=1 --file migrations/versions/0004_rename_task_objective.sql
.venv/bin/python scripts/seed_demo_data.py
.venv/bin/python scripts/generate_model_documents.py
```

启动只读 MCP 服务：

```bash
.venv/bin/orgsight-mcp
```

默认监听：

```text
http://127.0.0.1:8787/mcp
```

AgentTeams Worker 在 Docker 内可通过配置的宿主机地址访问该服务。

启动管理页面：

```bash
.venv/bin/orgsight-web
```

浏览器访问：

```text
http://127.0.0.1:8800
```

管理页面不会内置案例数据。历史案例、任务结果和 Markdown 报告均从 AgentTeams 的已完成任务接口读取。

## 测试

```bash
.venv/bin/python -m pytest -q
```

## 数据与安全边界

- 所有演示人物和组织数据均为合成数据；
- MCP 按 Task Grant 限制 Worker 可读取的人员、组织范围和工具；
- Manager、Leader 和 Worker 的运行凭证不写入 Agent package 或任务文本；
- PostgreSQL、MCP 和 AgentTeams Controller 不应直接暴露到公网；
- 对外展示时只公开管理页面，并建议增加身份验证和访问频率限制。
