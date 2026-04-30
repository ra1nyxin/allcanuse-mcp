# 值班功能总计划

本文档是 `allcanuse-mcp` 值班能力的临时总计划。目标不是只加一个 `wait`，而是把当前 MCP 从“同步工具箱”升级成“可长期值守、可恢复、可交接的执行中枢”。

## 总目标

- 让模型在用户不在线时仍能继续等待、巡检、观察和推进任务
- 让模型重连后能够恢复任务状态，而不是“断开一次就失忆”
- 让用户回来后能够直接查看“昨晚值班期间做了什么”
- 让等待行为从“死等时间”升级成“等条件、等事件、等后台任务完成”

## 设计原则

- 先做本地可用、跨平台、少依赖、强持久化
- 先做结构化后台任务，不做任意脚本调度器
- 任务必须可恢复、可查询、可取消、可交接
- 等待应优先支持“条件等待”，不是只支持 `sleep`
- 默认面向 Windows / Linux
- 默认不引入数据库，先用本地 JSON / JSONL 持久化

## 功能分层

### 第一层：同步等待工具

- [x] `wait`
- [x] `wait_until`
- [x] `get_scheduler_time`

### 第二层：条件等待工具

- [x] `wait_for_file`
- [x] `wait_for_process`
- [x] `wait_for_port`
- [x] `wait_for_http`
- [x] `wait_for_background_task`

### 第三层：后台任务调度与持久化

- [x] 本地任务目录初始化
- [x] 任务 JSON 持久化
- [x] 任务事件流 JSONL 持久化
- [x] 后台调度线程
- [x] 任务状态机
- [x] 轮询式条件检查器

### 第四层：后台任务管理工具

- [x] `create_background_task`
- [x] `list_background_tasks`
- [x] `get_background_task`
- [x] `cancel_background_task`
- [x] `pause_background_task`
- [x] `resume_background_task`
- [x] `summarize_background_task`

### 第五层：计划、事件、交接工具

- [x] `create_task_plan`
- [x] `update_task_step`
- [x] `append_task_event`
- [x] `record_task_artifact`
- [x] `mark_task_waiting_for_user`
- [x] `mark_task_waiting_for_condition`
- [x] `get_task_handoff`

### 第六层：文档与模型提示

- [x] 主提示词加入值班能力工作方式
- [x] README 更新
- [x] `docs/TOOLS.zh-CN.md` 更新
- [x] `docs/USAGE.zh-CN.md` 更新
- [x] 指南资源加入值班工作流

### 第七层：测试

- [x] 同步等待测试
- [x] 条件等待测试
- [x] 后台任务持久化测试
- [x] 后台任务状态流转测试
- [x] Server 工具注册测试

## 第一版实现范围

第一版先做“真正可用”的值班 MVP，不追求一次把所有高级能力做满。

### 第一版必须实现

- [x] `wait`
- [x] `wait_until`
- [x] `get_scheduler_time`
- [x] `wait_for_file`
- [x] `wait_for_process`
- [x] `wait_for_port`
- [x] `wait_for_http`
- [x] `create_background_task`
- [x] `list_background_tasks`
- [x] `get_background_task`
- [x] `cancel_background_task`
- [x] `pause_background_task`
- [x] `resume_background_task`
- [x] `wait_for_background_task`
- [x] `create_task_plan`
- [x] `update_task_step`
- [x] `append_task_event`
- [x] `record_task_artifact`
- [x] `summarize_background_task`

### 第一版允许暂缓

- [x] `wait_for_window`
- [x] `wait_for_desktop_change`
- [ ] 自动通知用户
- [ ] 复杂重试策略编辑器
- [ ] 多模型抢占 / 任务认领机制
- [ ] 通用任意工具编排执行器

## 推荐任务状态机

- `pending`
- `running`
- `waiting`
- `waiting_for_user`
- `waiting_for_condition`
- `paused`
- `completed`
- `failed`
- `cancelled`

## 推荐任务类型

- `sleep`
- `wait_file`
- `wait_process`
- `wait_port`
- `wait_http`
- `wait_window`
- `wait_desktop_change`

后续可扩展：

- `wait_network`
- `desktop_watch`
- `periodic_http_probe`

## 本地持久化目录

建议目录：

- `runtime/tasks/index.json`
- `runtime/tasks/<task_id>.json`
- `runtime/tasks/<task_id>.events.jsonl`
- `runtime/tasks/<task_id>.artifacts.json`

## 工具行为要求

### `wait`

- 接收毫秒数
- 返回实际等待时长
- 允许模型短暂停顿后继续执行

### `wait_until`

- 接收 ISO 8601 时间
- 自动处理本地时区和 UTC
- 如果目标时间已过，立即返回

### 条件等待类

- 都应支持：
  - `timeout_ms`
  - `poll_interval_ms`
  - 详细返回检查次数、最后一次观测结果

### 后台任务类

- 创建后立刻持久化
- 任务状态变更必须写盘
- 事件追加必须写入事件流
- 模型断线后，任务仍能继续被调度器轮询

## 模型使用建议

- 短暂停顿时：优先用 `wait`
- 等时间点时：优先用 `wait_until`
- 等外部状态变化时：优先用 `wait_for_*`
- 用户长时间离开时：优先把任务托管成 `background_task`
- 任务需要交接时：优先生成 `summarize_background_task` / `get_task_handoff`
- 多文件结果要发布时：先 `zip_paths` 再 `upload_file`

## 当前开发顺序

1. 写入本计划
2. 新建 `duty` 核心模块
3. 实现同步等待与条件等待
4. 实现后台任务持久化与调度器
5. 暴露 MCP tools
6. 同步文档与模型提示
7. 补测试并验证

## 当前轮次目标

本轮直接完成第一版值班 MVP：

- [x] 计划已写入根目录 `TODO.md`
- [x] 值班核心模块已实现
- [x] MCP tools 已注册
- [x] 文档已同步
- [x] 测试已通过
