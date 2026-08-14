---
name: modeling-project-state
description: 将已有项目材料中的目标、任务、里程碑、负责人、依赖、阻塞和业务事件整理为项目状态快照。仅在调用方已经提供明确 project_id 和项目原始材料时使用。
---

# 项目状态建模

## 目标与边界

把当前已知项目事实组织成可供风险分析和互动模拟读取的状态快照。此 Skill 不预测后果、不评价人员表现、不提出干预方案；不确定项必须标为缺失或待确认。

当前 GOAI 数据库没有项目记录时，不调用此 Skill。不得根据组织档案、人物模型或关系快照自行构造项目；宿主应直接返回 `PROJECT_CONTEXT_MISSING`。

## 输入

调用方提供：`project_id`、项目原始材料、`organization_snapshot`、可选关系快照和已确认事件事实。所有任务、人员与组织单元引用都必须来自输入材料和组织快照。

## 工作步骤

1. 以目标、约束、里程碑和当前事件固定项目范围与时间线。
2. 提取工作项、负责角色、前置依赖、决策点和已确认阻塞；区分事实和待确认状态。
3. 对依赖只描述已知方向，不估计未提供的工期或资源。
4. 将信息缺口写成会影响何种项目判断的具体问题。
5. 输出严格 JSON。

## 按需参考

- 任务依赖和阻塞的统一写法见 [项目状态快照口径](references/project-state-guidance.md)。

## 输出 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["result_type", "project_id", "project_snapshot_id", "snapshot_date", "goal", "constraints", "milestones", "work_items", "dependencies", "blockers", "decision_points", "evidence", "missing_information", "confidence"],
  "properties": {
    "result_type": {"const": "project_state_snapshot"}, "project_id": {"type": "string"}, "project_snapshot_id": {"type": "string"}, "snapshot_date": {"type":"string","format":"date"}, "goal": {"type": "string"}, "constraints": {"type": "array", "items": {"type": "string"}},
    "milestones": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["name", "date", "status"], "properties": {"name": {"type": "string"}, "date": {"type": "string"}, "status": {"type": "string", "enum": ["not_started", "in_progress", "at_risk", "blocked", "completed", "unknown"]}}}},
    "work_items": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["work_item_id", "name", "owner", "status"], "properties": {"work_item_id": {"type": "string"}, "name": {"type": "string"}, "owner": {"type": "string"}, "status": {"type": "string"}}}},
    "dependencies": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["predecessor", "successor", "status"], "properties": {"predecessor": {"type": "string"}, "successor": {"type": "string"}, "status": {"type": "string"}}}},
    "blockers": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["description", "affected_work_items", "status"], "properties": {"description": {"type": "string"}, "affected_work_items": {"type": "array", "items": {"type": "string"}}, "status": {"type": "string"}}}},
    "decision_points": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["description", "owner", "deadline"], "properties": {"description": {"type": "string"}, "owner": {"type": "string"}, "deadline": {"type": "string"}}}},
    "evidence": {"type": "array", "items": {"type": "string"}}, "missing_information": {"type": "array", "items": {"type": "string"}}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```
