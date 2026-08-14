---
name: designing-intervention-options
description: 围绕明确的管理或协作目标、约束和底线，基于一个或多个已完成的团队或项目诊断生成可比较的干预方案。当管理者已有诊断依据并需要选择行动路径时使用。
---

# 干预方案设计

## 目标与边界

在已知事实和明确约束下设计 2-3 个实质不同的方案。方案是建议，不是自动执行命令；不得承诺确定结果，不得绕过权限，不能把模拟结果写成已发生事实。

此 Skill 不强制要求项目输入。可以基于团队角色生态、团队健康或协作结构诊断工作；若目标明确指向项目，则必须同时提供项目状态或项目风险结果。没有任何有效诊断结果时不调用。

## 输入与步骤

输入：`management_goal`、`constraints`、`bottom_lines`、至少一个已完成的诊断结果及其 `result_ref`，以及可选项目状态、项目风险或模拟结果。

1. 明确目标、成功指标、约束和不可逾越底线；目标不清时停止方案生成并记录缺失信息。
2. 只使用输入诊断已支持的风险、资源和可调整变量，形成 2-3 个不同机制的方案。
3. 每个方案写清前置条件、顺序动作、责任角色、所需支持、条件性结果、验证指标、风险、护栏和回退信号。
4. 把模拟结果标为情境参考；所有方案都必须保留人工确认。
5. 只输出严格 JSON。

## 按需参考

- 方案对比与变更边界见 [管理干预设计口径](references/management-intervention-guidance.md)。

## 输出 JSON Schema

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "type":"object",
  "additionalProperties":false,
  "required":["result_type","management_goal","constraints","bottom_lines","input_result_refs","options","comparison_summary","missing_information","confidence"],
  "properties":{
    "result_type":{"const":"intervention_option_design"},
    "management_goal":{"type":"string"},
    "constraints":{"type":"array","items":{"type":"string"}},
    "bottom_lines":{"type":"array","items":{"type":"string"}},
    "input_result_refs":{"type":"array","minItems":1,"items":{"type":"string"}},
    "options":{"type":"array","minItems":2,"maxItems":3,"items":{"type":"object","additionalProperties":false,"required":["option_id","name","strategic_stance","preconditions","actions","required_support","expected_outcomes","validation_metrics","risks","guardrails","rollback_signals","evidence"],"properties":{"option_id":{"type":"string"},"name":{"type":"string"},"strategic_stance":{"type":"string"},"preconditions":{"type":"array","items":{"type":"string"}},"actions":{"type":"array","minItems":1,"items":{"type":"object","additionalProperties":false,"required":["sequence","action","owner_role","timing"],"properties":{"sequence":{"type":"integer","minimum":1},"action":{"type":"string"},"owner_role":{"type":"string"},"timing":{"type":"string"}}}},"required_support":{"type":"array","items":{"type":"string"}},"expected_outcomes":{"type":"array","items":{"type":"string"}},"validation_metrics":{"type":"array","items":{"type":"string"}},"risks":{"type":"array","items":{"type":"string"}},"guardrails":{"type":"array","items":{"type":"string"}},"rollback_signals":{"type":"array","items":{"type":"string"}},"evidence":{"type":"array","items":{"type":"string"}}}}},
    "comparison_summary":{"type":"string"},
    "missing_information":{"type":"array","items":{"type":"string"}},
    "confidence":{"type":"number","minimum":0,"maximum":1}
  }
}
```
