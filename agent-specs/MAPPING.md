# GOAI Agent 到 AgentTeams 配置映射

> 状态：`role-and-position-analysis-worker` 的 package 源目录、ZIP artifact 与静态 YAML 已生成；上传、`agt apply`、安装与启动均未做。其他 Agent 的 package 状态以各自目录为准。

本表只记录将来的生成去向，避免把角色定义、AgentTeams package 和 AgentTeams 资源 YAML 混为一层。

| Agent | 类型 | 角色源 | 未来 package 源目录 | 未来资源 YAML | Team / 关系 | GOAI Skill 副本 |
| --- | --- | --- | --- | --- | --- | --- |
| `profilemesh-manager` | Manager | `profilemesh-manager/AGENT.md` | `packages/profilemesh-manager/` | `manifests/manager/profilemesh-manager.yaml` | 委派至四个 Team Leader | 无 |
| `talent-role-insight-lead` | Team Leader / Worker | `talent-role-insight-lead/AGENT.md` | `packages/talent-role-insight-lead/` | `manifests/workers/talent-role-insight-lead.yaml` | `talent-role-insight` 的 Leader | 无 |
| `person-profile-worker` | Worker | `person-profile-worker/AGENT.md` | `packages/person-profile-worker/` | `manifests/workers/person-profile-worker.yaml` | `talent-role-insight` | `modeling-roles` |
| `role-and-position-analysis-worker` | Worker | `role-and-position-analysis-worker/AGENT.md` | `packages/role-and-position-analysis-worker/` | `manifests/workers/role-and-position-analysis-worker.yaml` | `talent-role-insight` | `analyzing-role-and-position` |
| `team-role-ecology-worker` | Worker | `team-role-ecology-worker/AGENT.md` | `packages/team-role-ecology-worker/` | `manifests/workers/team-role-ecology-worker.yaml` | `talent-role-insight` | `assessing-team-role-ecology` |
| `collaboration-governance-lead` | Team Leader / Worker | `collaboration-governance-lead/AGENT.md` | `packages/collaboration-governance-lead/` | `manifests/workers/collaboration-governance-lead.yaml` | `collaboration-governance` 的 Leader | 无 |
| `formal-authority-worker` | Worker | `formal-authority-worker/AGENT.md` | `packages/formal-authority-worker/` | `manifests/workers/formal-authority-worker.yaml` | `collaboration-governance` | 无；方法边界待确认 |
| `collaboration-network-worker` | Worker | `collaboration-network-worker/AGENT.md` | `packages/collaboration-network-worker/` | `manifests/workers/collaboration-network-worker.yaml` | `collaboration-governance` | `diagnosing-collaboration-structure`、`modeling-collaboration-relationships` |
| `governance-deviation-worker` | Worker | `governance-deviation-worker/AGENT.md` | `packages/governance-deviation-worker/` | `manifests/workers/governance-deviation-worker.yaml` | `collaboration-governance` | 无；方法边界待确认 |
| `business-operations-lead` | Team Leader / Worker | `business-operations-lead/AGENT.md` | `packages/business-operations-lead/` | `manifests/workers/business-operations-lead.yaml` | `business-operations` 的 Leader | 无 |
| `project-state-worker` | Worker | `project-state-worker/AGENT.md` | `packages/project-state-worker/` | `manifests/workers/project-state-worker.yaml` | `business-operations` | `modeling-project-state` |
| `task-dependency-worker` | Worker | `task-dependency-worker/AGENT.md` | `packages/task-dependency-worker/` | `manifests/workers/task-dependency-worker.yaml` | `business-operations` | `modeling-project-state` |
| `operations-risk-worker` | Worker | `operations-risk-worker/AGENT.md` | `packages/operations-risk-worker/` | `manifests/workers/operations-risk-worker.yaml` | `business-operations` | `analyzing-project-collaboration-risk` |
| `management-decision-simulation-lead` | Team Leader / Worker | `management-decision-simulation-lead/AGENT.md` | `packages/management-decision-simulation-lead/` | `manifests/workers/management-decision-simulation-lead.yaml` | `management-decision-simulation` 的 Leader | 无 |
| `diagnosis-synthesis-worker` | Worker | `diagnosis-synthesis-worker/AGENT.md` | `packages/diagnosis-synthesis-worker/` | `manifests/workers/diagnosis-synthesis-worker.yaml` | `management-decision-simulation` | 无；是否独立运行待确认 |
| `intervention-planner-worker` | Worker | `intervention-planner-worker/AGENT.md` | `packages/intervention-planner-worker/` | `manifests/workers/intervention-planner-worker.yaml` | `management-decision-simulation` | `designing-intervention-options` |
| `team-simulation-worker` | Worker | `team-simulation-worker/AGENT.md` | `packages/team-simulation-worker/` | `manifests/workers/team-simulation-worker.yaml` | `management-decision-simulation` | `simulating-team-interactions` |
| `plan-validation-worker` | Worker | `plan-validation-worker/AGENT.md` | `packages/plan-validation-worker/` | `manifests/workers/plan-validation-worker.yaml` | `management-decision-simulation` | 无；方法边界待确认 |

## Team 资源映射

| Team | 未来 Team YAML | Leader | 成员 |
| --- | --- | --- | --- |
| `talent-role-insight` | `manifests/teams/talent-role-insight.yaml` | `talent-role-insight-lead` | `person-profile-worker`、`role-and-position-analysis-worker`、`team-role-ecology-worker` |
| `collaboration-governance` | `manifests/teams/collaboration-governance.yaml` | `collaboration-governance-lead` | `formal-authority-worker`、`collaboration-network-worker`、`governance-deviation-worker` |
| `business-operations` | `manifests/teams/business-operations.yaml` | `business-operations-lead` | `project-state-worker`、`task-dependency-worker`、`operations-risk-worker` |
| `management-decision-simulation` | `manifests/teams/management-decision-simulation.yaml` | `management-decision-simulation-lead` | `diagnosis-synthesis-worker`、`intervention-planner-worker`、`team-simulation-worker`、`plan-validation-worker` |

## 生成前约束

- 每个 package 源目录与 YAML 已在表中路径生成。YAML 的 `spec.package` 指向将来上传后的 `packages/<agent-name>.zip`，并不表示 ZIP 已上传或可被 Controller 访问。
- 每个 package 只复制表中列出的 GOAI Skill；根目录 `skills/` 才是 Skill 的维护源。
- 每个 Worker 及 Team Leader 都会有一个 Worker YAML；Leader 在 Team YAML 内通过 `role: team_leader` 标注，而不是单独一种 AgentTeams 资源类型。
- 生成 YAML 前必须确定真实模型 ID 和 runtime；不使用占位模型或假凭证。
- 即使 YAML 生成，第一版也只写 `state: Stopped`，不执行 `agt apply`。
