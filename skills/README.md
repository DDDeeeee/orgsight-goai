# OrgSight Skills

此目录是 GOAI 领域 Skill 的唯一源文件位置。每个子目录都可独立作为 OpenClaw/AgentTeams Worker 工作区中的 `skills/<skill-name>/` 使用。

```text
orgsight-goai/skills/<skill-name>/
  SKILL.md
  references/
```

部署时，按需要把本目录中的一个或多个 Skill 复制进 Worker package 的 `skills/` 目录；AgentTeams 会在 Worker 工作区发现 `SKILL.md`。不要把这些领域 Skill 复制到 AgentTeams 仓库的内置 Skill 目录，也不要将它们作为 AgentTeams `spec.skills` 的内置 Skill 名称。

当前九个 Skill 只定义领域工作流和严格 JSON 输出。它们不直接访问 PostgreSQL，也不直接改写模型 Markdown；运行宿主负责将经过授权的冻结快照作为输入提供，并将通过校验的 JSON 输出写回 GOAI。

当前输入契约以以下正式数据为准：

- 人物档案：基本信息、环境背景、言语/行为/互动模式、关键事件和主观感知；
- 人物模型：专业优势、大五、MBTI、九型、阴暗人格、核心动机、职场动态、关系动态和综合侧写；
- 协作关系：无方向成员对、关系类型、`valence`、`salience`、合并 `summary` 和 `risk`，不包含证据摘要；
- 团队分析范围：`analysis_scope{scope_id, member_ids}`，其中 `scope_id` 使用正式组织或组织单元 ID，不使用未在正式组织快照中定义的临时标识；
- 项目状态：仅在数据库已有项目材料后提供。当前没有项目记录，项目状态建模和项目协作风险分析不得被调用来补造案例。

版本、状态、数据库关联和 Markdown 文件定位由运行宿主及 PostgreSQL 管理，不重复写入模型 Markdown 正文。
