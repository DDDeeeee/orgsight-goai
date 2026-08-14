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
4. 输出证据、缺失信息和置信度；只输出严格 JSON。

## 按需参考

- 角色定义与判断边界见 [贝尔宾团队角色](references/belbin-team-roles.md)。

## 输出 JSON Schema

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
