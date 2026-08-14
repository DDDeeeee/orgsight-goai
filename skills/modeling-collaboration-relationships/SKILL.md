---
name: modeling-collaboration-relationships
description: 将团队协作事实和关系描述整理为成员对形式的协作关系快照。当需要建立或更新团队实际协作网络，并以合并描述表达双方协作方式时使用。
---

# 协作关系建模

## 目标与边界

输出的是实际协作网络，不是正式组织图，也不是成员之间的好恶判断。每条边代表一个无序成员对，以一段综合描述说明双方当前的协作方式，不拆成 A 到 B 和 B 到 A。关系快照只代表当前时间点；不得覆盖或推断未提供的历史。

## 输入

调用方提供：`relationship_snapshot_id`、`snapshot_date`、`organization_snapshot`、相关 `person_profiles`、`person_models`、关系原始描述或关系 Note、`existing_edges`（可为空）。端点只可使用组织快照中存在的 `person_id`。

## 工作步骤

1. 先从正式架构中识别职责接口，再从事件和描述中识别实际信息流、资源流、决策依赖和信任/摩擦。
2. 只有现有材料足以说明稳定协作方式时才创建或更新成员对；信息不足时不补造边。
3. 关系类型应面向协作机制，如执行依赖、信息转接、复核、资源协调、竞争与互补。
4. `summary` 用一到两句话合并描述双方协作方式；`risk` 只写这段关系可能带来的主要协作风险。
5. `valence` 只表示当前关系整体为正向、中性或负向；`salience` 1-5 表示关系对团队运行的重要程度，不代表好坏。
6. 当前关系边不保存证据摘要。需要证据时读取或另建独立关系 Note，不把 Note 内容复制进边。
7. 输出严格 JSON。

## 按需参考

- 关系类型、关系倾向和显著度见 [协作关系边口径](references/collaboration-edge-guidance.md)。

## 输出 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["result_type", "relationship_snapshot_id", "snapshot_date", "edges", "missing_information", "confidence"],
  "properties": {
    "result_type": {"const": "collaboration_relationship_snapshot"},
    "relationship_snapshot_id": {"type": "string"},
    "snapshot_date": {"type": "string", "format": "date"},
    "edges": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["member_a", "member_b", "relationship_type", "valence", "salience", "summary", "risk"], "properties": {"member_a": {"type": "string"}, "member_b": {"type": "string"}, "relationship_type": {"type": "string"}, "valence": {"type": "string", "enum": ["positive", "neutral", "negative"]}, "salience": {"type": "integer", "minimum": 1, "maximum": 5}, "summary": {"type": "string"}, "risk": {"type": "string"}}}},
    "missing_information": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```
