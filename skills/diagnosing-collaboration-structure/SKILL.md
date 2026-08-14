---
name: diagnosing-collaboration-structure
description: 对照指定组织范围内的正式权责与实际协作网络，识别影响力、桥接、依赖瓶颈、子群、边缘位置和职责失配。当管理者需要理解组织图之外的实际协作结构时使用。
---

# 协作结构诊断

## 目标与边界

区分正式权力与实际影响力，找出结构性协作风险。边缘位置不等于能力弱；子群不必然是负面派系；重要成员不必然是瓶颈。此 Skill 不输出个人策略或健康评分。

## 输入与步骤

输入：`analysis_scope{scope_id, member_ids}`、`organization_snapshot`、`relationship_snapshot`、`person_models` 和可选 `project_snapshot`。`scope_id` 必须来自组织快照中的组织或单元 ID。

1. 从正式岗位、汇报线和职责提取正式结构。
2. 从成员对关系的 `relationship_type`、`valence`、`salience`、`summary` 和 `risk` 提取实际网络。关系边没有方向字段时，不得自行恢复 A 到 B 或 B 到 A 的方向。
3. 分别识别正式负责人、实际影响者、桥接节点、真正的瓶颈、稳定子群与边缘位置。
4. 只在存在结构依据时输出节点或群组，区分事实依据和风险推断。
5. 输出严格 JSON。

## 按需参考

- 结构概念与误判边界见 [组织网络分析口径](references/organizational-network-analysis.md)。

## 输出 JSON Schema

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "type":"object", "additionalProperties":false,
  "required":["result_type","scope_id","snapshot_date","formal_structure_summary","actual_network_summary","power_and_influence_nodes","bridges","bottlenecks","clusters","peripheral_positions","role_mismatches","evidence","missing_information","confidence"],
  "properties":{
    "result_type":{"const":"collaboration_structure_diagnosis"}, "scope_id":{"type":"string"}, "snapshot_date":{"type":"string","format":"date"}, "formal_structure_summary":{"type":"string"}, "actual_network_summary":{"type":"string"},
    "power_and_influence_nodes":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["person_id","node_type","basis"],"properties":{"person_id":{"type":"string"},"node_type":{"type":"string","enum":["formal_leader","actual_influencer","information_node","resource_node"]},"basis":{"type":"array","items":{"type":"string"}}}}},
    "bridges":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["person_id","connects","basis"],"properties":{"person_id":{"type":"string"},"connects":{"type":"array","items":{"type":"string"}},"basis":{"type":"string"}}}},
    "bottlenecks":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["endpoint_id","dependency","risk"],"properties":{"endpoint_id":{"type":"string"},"dependency":{"type":"string"},"risk":{"type":"string"}}}},
    "clusters":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["member_ids","structure_basis","risk_or_value"],"properties":{"member_ids":{"type":"array","items":{"type":"string"}},"structure_basis":{"type":"string"},"risk_or_value":{"type":"string"}}}}, "peripheral_positions":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["person_id","basis","interpretation_boundary"],"properties":{"person_id":{"type":"string"},"basis":{"type":"string"},"interpretation_boundary":{"type":"string"}}}}, "role_mismatches":{"type":"array","items":{"type":"string"}}, "evidence":{"type":"array","items":{"type":"string"}}, "missing_information":{"type":"array","items":{"type":"string"}}, "confidence":{"type":"number","minimum":0,"maximum":1}
  }
}
```
