# GOAI AgentSpec 源文件

本目录保存 OrgSight 的 Agent 角色源文件，以及未来生成 AgentTeams 配置时所需的映射信息。它不是 AgentTeams runtime 源码，也不是可直接 `apply` 的部署包。

每个 `<agent-name>/AGENT.md` 定义一个未来 Agent 的：

- 身份与职责；
- system prompt；
- 所属 Team；
- 已绑定的 GOAI Skill（如有）；
- 未来工具权限和明确禁止事项；
- 当前是否允许运行。

## 目录边界

```text
agent-specs/
  registry.yaml                 # Manager、Team 与成员关系的角色总表
  MAPPING.md                    # 角色到未来 package / manifest 的审阅映射
  <agent-name>/AGENT.md         # 该 Agent 的唯一角色定义源
  packages/                     # 已生成的 AgentTeams package 源目录
  manifests/                    # 已生成、但尚未 apply 的静态资源 YAML
```

- `AGENT.md` 是角色、system prompt、GOAI Skill 绑定与权限边界的唯一维护来源。
- `packages/` 已放入每个 Agent 的 package 源内容：`manifest.json`、`config/SOUL.md`、`config/AGENTS.md`，以及按绑定复制的 GOAI Skills。QwenPaw 将身份和角色合并到 `SOUL.md`，因此没有独立 `IDENTITY.md`。
- `manifests/` 已放入 AgentTeams 的 1 个 `Manager`、17 个 `Worker`、4 个 `Team` 资源 YAML。所有 Manager / Worker YAML 均使用 `state: Stopped`。
- `MAPPING.md` 是生成前的检查表：它明确每个 Agent 将对应哪个 package、哪个资源 YAML、属于哪个 Team、挂载哪些现有 GOAI Skill。

当前完成的是静态配置：七个已有数据读取 Worker 的 YAML 已声明本机 GOAI MCP 地址，但没有生成或上传 ZIP artifact，没有执行 `agt apply`，没有配置模型 Base URL、Worker 凭证或环境变量，也没有启动任何 Agent。

真正接入 AgentTeams 时，以这些源文件和 `MAPPING.md` 为唯一配置输入：将每个 `packages/<agent-name>/` 打成 ZIP artifact、上传到 AgentTeams package storage，再使 YAML 中的 `spec.package` 指向该上传路径。项目根目录 `skills/` 仍是领域 Skill 的唯一维护位置。
