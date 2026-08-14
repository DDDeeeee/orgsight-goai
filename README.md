# OrgSight

#### 多 Agent 组织分析洞察系统

OrgSight 面向组织管理者，解决团队扩张时组织复杂度上升引入的管理难题。OrgSight 构建基于组织上下文的版本化组织快照，并基于 AgentTeams 构建多智能体分析框架。管理者只需将组织分析任务交给 Manager 或对应的团队 Leader，由 Leader 拆解任务、委派专业 Worker，在授权范围内查看组织、人员与协作数据，最终生成包含结论、依据、风险、信息缺口和置信度的结构化报告或决策建议。管理者或员工也可与 OrgSight 进行日常交流，OrgSight 会主动沉淀有价值的信息作为建模依据或组织上下文。

该项目参加 GOAI Agent Infra 赛道（目前仅为 Demo）。

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

仓库中还包含协作治理、业务运营和管理决策模拟等团队的 Agent 与 Skills 设计骨架。这些扩展团队尚未完成端到端验证。

## 测试样例：方宁销售代表岗位适配分析

### 输入

> 请评估方宁是否适合继续担任销售代表，重点分析她的岗位适配情况、协作优势和主要风险。

### 输出

网页案例展示：

![方宁销售代表岗位适配分析结果](examples/fangning-sales-fit/demo_result.png)

Worker 提交并由页面读取的完整结果：[查看 result.md](examples/fangning-sales-fit/result.md)。

## 演示数据

当前 Demo 使用的模拟组织基线：

- 22 名合成人员；
- 6 个正式组织单元；
- 正式岗位和汇报关系；
- 人物事实档案与人物职业模型。

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

- 本仓库负责业务数据、Agent/Skills 定义、只读 MCP、授权逻辑和展示页面；
- [AgentTeams](https://github.com/DDDeeeee/AgentTeams) fork 负责 Manager、Team Leader、Worker、Task、Room、Matrix 通信和运行生命周期。

运行完整 Demo 时，需要单独部署对应版本的 AgentTeams，并安装 `agent-specs/packages/` 中的 Agent package。

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

## 测试

```bash
.venv/bin/python -m pytest -q
```
