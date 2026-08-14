---
name: simulating-team-interactions
description: 基于冻结版本的组织、人物模型、协作关系和团队诊断，推演一个明确情境或干预下可能出现的协作变化与目标达成情况。当已有具体 scenario 并需要比较情境走向时使用；项目状态为可选输入。
---

# 团队互动模拟

## 目标与边界

输出是基于当前快照和明确假设的情境推演，不是未来事实。输入事实、模型判断和模拟推断必须分开；不使用快照时间之后的信息，不自动执行任何干预。

没有明确 `scenario.description` 或冻结基线引用时不调用。项目状态不是必需输入；没有项目上下文时，`project_impacts` 必须为空，不能自行构造项目。

## 输入与步骤

输入：`baseline_snapshot_refs`、冻结的组织/人物/关系/团队诊断、`scenario{description, time_horizon, management_goal}`、可选 `intervention_parameters` 和可选项目状态。

1. 固定基线引用、时间范围、情境变化和管理目标。
2. 识别受影响成员对、关键协作机制与传导条件；关系边没有方向字段时不得自行补造方向性事实。
3. 给出最可能、最坏、最好三个条件分支，分别说明团队关系、项目（如有）和目标影响。
4. `evidence` 只列输入引用；推演前提写入 `assumptions`，不混入事实。
5. 只输出严格 JSON。

## 按需参考

- 模拟中的事实、假设与证据分离见 [情境模拟口径](references/scenario-simulation-guidance.md)。

## 输出 JSON Schema

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$defs":{"branch":{"type":"object","additionalProperties":false,"required":["description","relationship_impact","project_impact","goal_impact"],"properties":{"description":{"type":"string"},"relationship_impact":{"type":"array","items":{"type":"string"}},"project_impact":{"type":"array","items":{"type":"string"}},"goal_impact":{"type":"string"}}}},
  "type":"object",
  "additionalProperties":false,
  "required":["result_type","simulation_run_id","baseline_snapshot_refs","scenario","assumptions","main_trajectory","branch_outcomes","relationship_impacts","project_impacts","goal_achievement_assessment","evidence","missing_information","confidence"],
  "properties":{
    "result_type":{"const":"team_interaction_simulation"},
    "simulation_run_id":{"type":"string"},
    "baseline_snapshot_refs":{"type":"array","minItems":1,"items":{"type":"string"}},
    "scenario":{"type":"object","additionalProperties":false,"required":["description","time_horizon","management_goal"],"properties":{"description":{"type":"string"},"time_horizon":{"type":"string"},"management_goal":{"type":"string"}}},
    "assumptions":{"type":"array","items":{"type":"string"}},
    "main_trajectory":{"type":"string"},
    "branch_outcomes":{"type":"object","additionalProperties":false,"required":["most_likely","worst_case","best_case"],"properties":{"most_likely":{"$ref":"#/$defs/branch"},"worst_case":{"$ref":"#/$defs/branch"},"best_case":{"$ref":"#/$defs/branch"}}},
    "relationship_impacts":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["member_a","member_b","change","summary"],"properties":{"member_a":{"type":"string"},"member_b":{"type":"string"},"change":{"type":"string","enum":["improve","worsen","change","uncertain"]},"summary":{"type":"string"}}}},
    "project_impacts":{"type":"array","items":{"type":"string"}},
    "goal_achievement_assessment":{"type":"string"},
    "evidence":{"type":"array","items":{"type":"string"}},
    "missing_information":{"type":"array","items":{"type":"string"}},
    "confidence":{"type":"number","minimum":0,"maximum":1}
  }
}
```
