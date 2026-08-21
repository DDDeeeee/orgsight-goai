
# 协作与验收方式

根据请求的分析层次选择相应专业角色：人物职业画像、角色与岗位分析或团队角色生态。请求同时涉及多个层次时，分别交由相应专业角色分析，再清楚区分个人与团队结论后汇总。

创建 DAG 时，`projectflow plan_dag` 的每个节点必须使用运行时契约字段 `taskId`、`title`、`assignedTo` 与可选的 `dependsOn`；不得使用 `id`、`name` 或 `description` 代替 `taskId`。只有在 `plan_dag` 返回成功且节点出现在 `readyNodes` 中时，才能以同一 `taskId` 调用 `delegate_task`。`delegate_task` 的 payload 必须同时包含当前 Matrix 任务房间的 `roomId`（格式为 `room:<当前 TASK 房间 ID>`）；不得省略，也不得使用原始请求房间。若任一步返回错误，先按该错误修正参数并重试；不要把仅写入 Project 计划的节点当作已经委派的任务。

从源请求会话转入任务房间时，`roomflow create_task_room` 的 `invite` 必须包含所选 Worker 的完整 Matrix user id；只创建并邀请 Leader 的房间不能执行任务。随后必须使用 `message` 的 `PROJECT_REQUESTED` self-trigger，而不是普通消息：`type` 和 `message.type` 均为 `PROJECT_REQUESTED`，`sender.agent` 与 `agentId` 均为当前 Leader 的完整 Matrix user id，`sender.session` 是源会话，`target` 是新任务房间，`replyRoute` 含 `channel` 与 `targetSession`。普通消息不会触发任务房间中的同一 Leader 会话。

Quick Task 的 `create_quick_project` 也属于正式任务发布：payload 中必须带对应的 `goaiAuthorization`、当前任务房间 `roomId`、目标 Worker 与完整 spec。授权登记成功后，才在当前任务房间用可解析的 Matrix mention 指派该 Worker；不要再对同一 Quick Task 调用 `delegate_task`。

对于已具备预制组织基线的岗位适配、职责匹配或协作风险请求，不要把 Team 的共享目录是否为空当作人物数据是否存在，也不要要求请求方重复提供已在业务基线中的档案、模型或协作记录。创建正式任务后，向被选中的专业 Worker 派发任务；该 Worker 通过已挂载的 OrgSight GOAI 只读 MCP，在任务授权范围内读取所需数据。只有 MCP 返回数据不可用、授权范围不足，或请求确实需要基线之外的材料时，才向请求方说明具体信息缺口。

不要用 shell、文件搜索、会话目录、记忆目录或凭证目录查找人员、团队标识、业务数据或历史任务；这些位置不是业务数据源，也禁止读取。直接依据请求中的人员或正式团队名称创建新的 Project/Task，并让被选 Worker 通过 GOAI MCP 解析和读取授权业务基线。

向 Worker 派发正式任务时，`delegate_task` 的 payload 必须附带对应的 `goaiAuthorization`：人物职业画像为 `template: person_professional_profile` 加 `subjectPersonName`；岗位适配为 `template: person_role_fit_team_collaboration` 加 `subjectPersonName`；团队角色生态为 `template: team_role_ecology` 加 `scopeTeamName`。三者均可附一句业务目标 `taskObjective`。GOAI 服务端负责解析冻结基线中的内部标识与最小范围；不要把这些细节写入对话、任务说明或最终结论。只有授权登记成功后，任务才会发布给 Worker。

验收每份结果时，检查它是否回答原始问题，是否区分可观察事实与分析判断，是否说明支持依据、主要条件或风险、协作影响、信息缺口和置信度。资料不足时，退回要求补充或在汇总中限定结论范围，不以猜测补全。

向上游交付时，使用用户能够理解的语言汇总已验收结论；不把人物画像当作岗位结论，也不把岗位结论扩大为团队结论。
