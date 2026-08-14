---
name: analyzing-project-collaboration-risk
description: 关联已有项目状态快照、协作路径、团队结构和事件事实，识别可能影响交付的等待、返工、升级阻塞和单点依赖风险。仅在已存在有效 project_state_snapshot 时使用。
---

# 项目协作风险分析

## 目标与边界

识别会影响项目交付的协作风险，而不是把所有不确定性都列为风险，也不直接提出干预方案。风险必须有明确的触发条件、影响路径和事实依据；严重度与可能性是当前快照下的判断，不是预测事实。

当前数据库没有项目记录或未提供有效 `project_state_snapshot` 时，不调用此 Skill。不得把组织中的一般协作风险改写成某个虚构项目风险；宿主应直接返回 `PROJECT_CONTEXT_MISSING`。

## 输入与步骤

输入：同一时间范围内的 `project_state_snapshot`、`relationship_snapshot`、`collaboration_structure_diagnosis`、相关 `person_models` 与已确认事件事实。

1. 先读取项目任务、依赖、阻塞和关键决策点。
2. 结合实际协作结构，识别等待、重复确认、返工、升级阻塞、单点依赖或信息不一致等风险。
3. 每项风险写清触发条件、影响路径、受影响工作项、早期信号和输入引用；关系边综合描述只能作为当前关系模型使用，不能伪装成独立 Evidence Note。
4. 按严重度与可能性排序；缺乏证据的项目放进缺失信息，不硬凑风险登记。
5. 输出严格 JSON。

## 按需参考

- 风险类别和依赖模式见 [项目协作风险分类](references/project-collaboration-risk-taxonomy.md)。

## 输出 JSON Schema

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "type":"object", "additionalProperties":false,
  "required":["result_type","project_id","project_snapshot_id","risk_register","summary","missing_information","confidence"],
  "properties":{
    "result_type":{"const":"project_collaboration_risk_analysis"}, "project_id":{"type":"string"}, "project_snapshot_id":{"type":"string"}, "summary":{"type":"string"},
    "risk_register":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["risk_id","risk_type","severity","likelihood","trigger_conditions","impact_path","affected_work_items","early_signals","evidence"],"properties":{"risk_id":{"type":"string"},"risk_type":{"type":"string","enum":["waiting","repeated_confirmation","rework","escalation_blockage","single_point_dependency","information_misalignment","responsibility_gap","other"]},"severity":{"type":"string","enum":["low","medium","high","critical"]},"likelihood":{"type":"string","enum":["low","medium","high"]},"trigger_conditions":{"type":"array","items":{"type":"string"}},"impact_path":{"type":"string"},"affected_work_items":{"type":"array","items":{"type":"string"}},"early_signals":{"type":"array","items":{"type":"string"}},"evidence":{"type":"array","items":{"type":"string"}}}}},
    "missing_information":{"type":"array","items":{"type":"string"}}, "confidence":{"type":"number","minimum":0,"maximum":1}
  }
}
```
