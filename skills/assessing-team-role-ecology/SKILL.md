---
name: assessing-team-role-ecology
description: 基于指定组织或组织单元范围内的成员职业模型、正式职责和当前关系评估角色覆盖、重叠、缺位与承载风险。当管理者需要理解一个明确范围内由谁承担哪些团队功能时使用。
---

# 团队角色生态评估

## 目标与边界

识别团队实际贡献角色与任务所需角色是否匹配。角色来自可观察贡献，不等于职位、性格标签或固定人设；同一成员可承担 1-3 种角色。此 Skill 不评价团队健康、不做结构网络诊断或管理建议。

## 输入与步骤

输入：同一快照下的 `analysis_scope{scope_id, member_ids}`、`person_models`、`organization_snapshot`、`relationship_snapshot` 和可选 `project_snapshot`。`scope_id` 必须是组织快照中的 `organization_id` 或 `unit_id`，不得使用未在正式组织快照中定义的临时标识。

1. 有项目输入时，从项目需求和正式职责识别角色能力；没有项目输入时，只评估当前组织日常运行所需角色，不补造项目需要。
2. 逐人判断实际贡献，最多分配 3 个角色，并附可观察依据。
3. 比较覆盖、重叠、缺位和关键角色集中度；不要仅因人数少认定角色缺失。
4. 先按下方 Schema 完成内部结构化自检，再将同一判断写入当前任务目录的用户可读 Markdown `result.md`。JSON 不单独作为交付物，也不额外输出 JSON 文件。

## 按需参考

- 角色定义与判断边界见 [贝尔宾团队角色](references/belbin-team-roles.md)。

## 输出 JSON Schema

## Markdown 正式交付

`result.md` 是本 Worker 的唯一正式结果。报告必须包含“分析范围、生态结论摘要、角色覆盖、角色重叠与缺位、关键角色集中与承载风险、成员贡献、依据、信息缺口、置信度”九个章节。

- 团队角色来自可观察贡献，不能等同于职位、性格标签或固定人设；成员贡献仅在现有材料支持时列出。
- **依据**使用 Markdown 表格，列为“编号、类型、内容、支持的判断、来源说明”；类型只能是“事实”“观察”或“推断”。
- 不把没有预制数据的团队健康、项目状态或项目事件补造为事实；资料不足时说明有限结论与缺口。
- 信息缺口只描述业务材料本身的缺失及其对判断的影响；不得说明授权范围、读取限制、既有系统数据、工具能力或运行条件。
- 不写任务 ID、房间号、内部标识、工具调用、文件路径、系统名、授权过程、模板名称或其他内部运行说明。

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "type":"object", "additionalProperties":false,
  "required":["result_type","scope_id","snapshot_date","member_role_contributions","role_coverage","overlaps","gaps","concentration_risks","evidence","missing_information","confidence"],
  "properties":{
    "result_type":{"const":"team_role_ecology_assessment"}, "scope_id":{"type":"string"}, "snapshot_date":{"type":"string","format":"date"},
    "member_role_contributions":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["person_id","role_keys","evidence"],"properties":{"person_id":{"type":"string"},"role_keys":{"type":"array","minItems":1,"maxItems":3,"items":{"type":"string","enum":["plant","monitor_evaluator","specialist","coordinator","teamworker","resource_investigator","shaper","implementer","completer_finisher"]}},"evidence":{"type":"array","items":{"type":"string"}}}}},
    "role_coverage":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["role_key","coverage_status","summary"],"properties":{"role_key":{"type":"string"},"coverage_status":{"type":"string","enum":["covered","weak","missing","overloaded"]},"summary":{"type":"string"}}}},
    "overlaps":{"type":"array","items":{"type":"string"}}, "gaps":{"type":"array","items":{"type":"string"}}, "concentration_risks":{"type":"array","items":{"type":"string"}}, "evidence":{"type":"array","items":{"type":"string"}}, "missing_information":{"type":"array","items":{"type":"string"}}, "confidence":{"type":"number","minimum":0,"maximum":1}
  }
}
```
