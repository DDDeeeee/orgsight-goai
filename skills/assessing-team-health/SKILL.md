---
name: assessing-team-health
description: 基于指定组织范围内的人物档案、人物模型和协作关系评估生命周期、心理安全、冲突、目标承诺、责任承担和结果导向。当管理者需要判断一个明确组织范围的当前健康状态及风险传导时使用。
---

# 团队健康评估

## 目标与边界

给出团队层面的健康信号和风险传导，不将团队问题归咎于单一个人，也不直接输出干预方案。评分是当前快照下的模型估计，必须说明输入依据和置信度，不能伪装成正式测量。

## 输入与步骤

输入：`analysis_scope{scope_id, member_ids}`、`organization_snapshot`、`person_profiles`、`person_models`、`relationship_snapshot`、可选 `project_snapshot` 和可选角色生态结果。`scope_id` 必须来自组织快照中的组织或单元 ID。

1. 判断团队更接近 forming、storming、norming、performing 或 adjourning 的哪一阶段。
2. 分别评估心理安全、建设性冲突、目标承诺、责任承担与结果导向，0-100 分统一表示健康程度。
3. 若发现低层问题可能传导为上层问题，明确说明链路；证据不够时写入缺失信息。关系边的 `summary` 是当前关系模型，不等同于独立 Evidence Note。
4. 只输出严格 JSON。

## 按需参考

- 团队阶段与五大障碍见 [团队健康理论口径](references/team-health-frameworks.md)。

## 输出 JSON Schema

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "type":"object", "additionalProperties":false,
  "required":["result_type","scope_id","snapshot_date","lifecycle","health_dimensions","risk_propagation","health_summary","evidence","missing_information","confidence"],
  "properties":{
    "result_type":{"const":"team_health_assessment"}, "scope_id":{"type":"string"}, "snapshot_date":{"type":"string","format":"date"},
    "lifecycle":{"type":"object","additionalProperties":false,"required":["stage","score","summary"],"properties":{"stage":{"type":"string","enum":["forming","storming","norming","performing","adjourning","unknown"]},"score":{"type":"integer","minimum":0,"maximum":100},"summary":{"type":"string"}}},
    "health_dimensions":{"type":"array","minItems":5,"maxItems":5,"items":{"type":"object","additionalProperties":false,"required":["key","score","summary","evidence"],"properties":{"key":{"type":"string","enum":["psychological_safety","constructive_conflict","goal_commitment","accountability","result_orientation"]},"score":{"type":"integer","minimum":0,"maximum":100},"summary":{"type":"string"},"evidence":{"type":"array","items":{"type":"string"}}}}},
    "risk_propagation":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["source_dimension","target_dimension","propagation_mechanism"],"properties":{"source_dimension":{"type":"string"},"target_dimension":{"type":"string"},"propagation_mechanism":{"type":"string"}}}}, "health_summary":{"type":"string"}, "evidence":{"type":"array","items":{"type":"string"}}, "missing_information":{"type":"array","items":{"type":"string"}}, "confidence":{"type":"number","minimum":0,"maximum":1}
  }
}
```
