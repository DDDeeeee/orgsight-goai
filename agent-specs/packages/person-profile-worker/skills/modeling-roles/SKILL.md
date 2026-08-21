---
name: modeling-roles
description: 基于已授权的人物职场档案、正式岗位和当前协作关系形成可读的人物职业画像。当需要理解个人工作特征、职业优势、发展关注点或协作特点时使用。
---

# 角色建模

## 目标与边界

将人物档案转化为可供管理者理解的职业画像，以可观察职场行为为主体。心理学概念只可在确有多条材料支撑时，作为对工作偏好、协作方式与压力反应的谨慎解释。

不要从单一事件或主观感知推出稳定人格结论。`subjective_impressions` 的权重低于档案中的行为、互动和关键事件。信息不足时，不补造类型、分数或特质，直接说明对应的信息缺口并降低置信度。

## 输入

调用方提供同一冻结快照内的：

- `person_profile`：包含基本信息、环境背景、`verbal_patterns`、`behavioral_patterns`、`interaction_patterns`、`key_events` 和 `subjective_impressions`；
- `formal_position`：来自正式组织快照的岗位、所属单元和汇报关系；
- `related_relationships`：只包含目标人物的当前成员对关系；
- `current_model`（可为空）和目标 `model_version`。

## 工作步骤

1. 先确认岗位、职责边界、环境背景和可观察事实，区分事实、主观感知与推断。
2. 归纳专业优势和工作、沟通、决策、压力、冲突、权力、信任与边界模式。
3. 仅在多个独立线索支持时给出谨慎的工作行为解释；不主动输出人格类型、人格量表、心理机制或阴暗人格标签。
4. `evidence` 使用输入字段引用，例如 `person_profile.behavioral_patterns[2]`；记录冲突线索和缺失信息。
5. 先按下方 Schema 完成内部结构化自检，再将同一判断写入当前任务目录的用户可读 Markdown `result.md`。JSON 不单独作为交付物，也不额外输出 JSON 文件。

## 按需参考

- 需要判断心理维度如何谨慎映射为职场行为时，阅读 [职业行为与心理解释](references/workplace-behavior-and-psychology.md)。

## 输出 JSON Schema

## Markdown 正式交付

`result.md` 是本 Worker 的唯一正式结果。报告必须包含“职业画像摘要、工作特征、职业优势、发展关注点、协作特点、依据、信息缺口、置信度”八个章节。

- 先给结论，再说明可观察事实、他人感受与分析判断；不得把心理类型当作诊断或事实。
- **依据**使用 Markdown 表格，列为“编号、类型、内容、支持的判断、来源说明”；类型只能是“事实”“观察”或“推断”。
- 资料不足时给出有限结论，说明缺口及其影响；置信度使用“高”“中”“低”，不使用未经计算的精确百分比。
- 只写人物相关内容；不写任务 ID、房间号、内部标识、工具调用、文件路径、系统名、授权过程、模板名称、模型使用说明或与人物无关的边界声明。

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "type_hypothesis": {"type":"object","additionalProperties":false,"required":["type","confidence","reasoning"],"properties":{"type":{"type":"string"},"confidence":{"type":"number","minimum":0,"maximum":1},"reasoning":{"type":"string"}}},
    "dark_trait": {"type":"object","additionalProperties":false,"required":["level","confidence","reasoning"],"properties":{"level":{"type":"string","enum":["low","medium","high","unknown"]},"confidence":{"type":"number","minimum":0,"maximum":1},"reasoning":{"type":"string"}}}
  },
  "type":"object",
  "additionalProperties":false,
  "required":["result_type","person_id","model_version","professional_strengths","big_five","mbti","enneagram","dark_traits","core_fears","core_desires","defense_mechanisms","workplace_dynamics","relationship_dynamics","summary_profile","evidence","missing_information","confidence"],
  "properties":{
    "result_type":{"const":"person_role_model"},
    "person_id":{"type":"string"},
    "model_version":{"type":"integer","minimum":1},
    "professional_strengths":{"type":"array","minItems":1,"maxItems":5,"items":{"type":"string"}},
    "big_five":{"type":"object","additionalProperties":false,"required":["openness","conscientiousness","extraversion","agreeableness","emotional_stability","reasoning"],"properties":{"openness":{"type":"integer","minimum":0,"maximum":100},"conscientiousness":{"type":"integer","minimum":0,"maximum":100},"extraversion":{"type":"integer","minimum":0,"maximum":100},"agreeableness":{"type":"integer","minimum":0,"maximum":100},"emotional_stability":{"type":"integer","minimum":0,"maximum":100},"reasoning":{"type":"string"}}},
    "mbti":{"$ref":"#/$defs/type_hypothesis"},
    "enneagram":{"$ref":"#/$defs/type_hypothesis"},
    "dark_traits":{"type":"object","additionalProperties":false,"required":["narcissism","machiavellianism","psychopathy"],"properties":{"narcissism":{"$ref":"#/$defs/dark_trait"},"machiavellianism":{"$ref":"#/$defs/dark_trait"},"psychopathy":{"$ref":"#/$defs/dark_trait"}}},
    "core_fears":{"type":"array","maxItems":3,"items":{"type":"string"}},
    "core_desires":{"type":"array","maxItems":3,"items":{"type":"string"}},
    "defense_mechanisms":{"type":"array","maxItems":4,"items":{"type":"string"}},
    "workplace_dynamics":{"type":"object","additionalProperties":false,"required":["work_style","communication_style","decision_making_style","stress_response","conflict_style","power_dynamics","trust_building","boundary_style"],"properties":{"work_style":{"type":"string"},"communication_style":{"type":"string"},"decision_making_style":{"type":"string"},"stress_response":{"type":"string"},"conflict_style":{"type":"string"},"power_dynamics":{"type":"string"},"trust_building":{"type":"string"},"boundary_style":{"type":"string"}}},
    "relationship_dynamics":{"type":"string"},
    "summary_profile":{"type":"string"},
    "evidence":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["claim","source_ref","confidence"],"properties":{"claim":{"type":"string"},"source_ref":{"type":"string"},"confidence":{"type":"number","minimum":0,"maximum":1}}}},
    "missing_information":{"type":"array","items":{"type":"string"}},
    "confidence":{"type":"number","minimum":0,"maximum":1}
  }
}
```
