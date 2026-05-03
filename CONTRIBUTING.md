# Contributing

感谢对 `allcanuse-mcp` 的关注。

这个项目的目标很直接：给模型暴露一组在 Windows / Linux 实验环境里真正能用、能组合、能持续维护的 MCP 工具。  
贡献时请优先围绕这件事本身，不要把仓库拉向“大而散”的演示集合。

## 适合贡献的方向

- 修复工具行为错误、跨平台兼容问题、回归问题
- 提升 Windows / Linux 下的稳定性和可用性
- 减少对小众、易失效第三方库的依赖
- 为现有工具补更好的错误信息、边界处理、超时控制
- 增加和当前定位一致的新工具
- 完善提示词、guides、客户端接入文档、工具说明
- 补测试，尤其是回归测试和跨平台回退逻辑测试

## 不建议的方向

- 引入大量和项目定位无关的炫技功能
- 为单一小众场景增加沉重依赖
- 没有测试和文档支撑的大改动
- 只改 README 或描述文案，但代码行为没有同步核对
- 破坏已有工具名、参数名、返回结构的兼容性而不说明

## 开发环境

要求：

- Python `3.11+`
- Windows 或 Linux

建议先安装依赖：

```powershell
pip install -r requirements.txt
```

如果需要本地可编辑安装：

```powershell
pip install -e .
```

## 代码组织

- `src/allcanuse_mcp/core/`: 底层实现
- `src/allcanuse_mcp/tools/`: MCP tool 注册层
- `src/allcanuse_mcp/descriptions.py`: 工具说明、guides、模型提示词
- `src/allcanuse_mcp/server.py`: MCP Server 注册与 prompt/resource 暴露
- `tests/`: 单元测试与回归测试
- `docs/`: 面向用户和客户端接入的文档

一般来说：

- 新能力先落到底层 `core`
- 再在 `tools` 里注册为 MCP 工具
- 再补 `descriptions.py` 里的工具说明、示例和必要的 workflow / prompt 引导
- 最后补测试与文档

## 提交前最低要求

至少做这些检查：

```powershell
python -m compileall src tests run_server.py
$env:PYTHONPATH=(Resolve-Path .\src).Path
python -m unittest discover -s tests -v
```

如果改动涉及：

- 新工具：必须补工具级测试
- 返回结构变化：必须补回归测试
- 提示词、guide、resource、prompt 变化：最好补 `tests/test_server_tools.py`
- 文档里的接入流程变化：至少手工核一遍 README 和对应 `docs/`

## 提交建议

推荐一个贡献最小闭环：

1. 先开 issue 或先描述问题边界
2. 再做最小必要修改
3. 补测试
4. 补文档
5. 确认本地测试通过
6. 再提交 PR

请尽量避免在同一个 PR 里混入：

- 无关重构
- 大量格式化
- 顺手改一堆不相关文件

## 工具设计约定

新增或修改工具时，请尽量遵守下面这些约定：

- 优先跨平台；如果不能跨平台，要明确平台差异
- 长时或网络工具尽量允许调用方显式传 `timeout_ms`
- 尽量返回结构化字段，而不是只返回一段大文本
- 错误时尽量返回 `ok: false` 与可操作的错误信息
- 能不用脆弱小众依赖就不用，优先标准库、系统命令或本地实现
- 如果某能力需要可选依赖，说明要写清楚，报错要清楚
- 不要轻易改已有工具名、参数名、返回字段名

## 提示词与文档约定

这个项目不只是工具集合，模型提示词和 guides 也是行为的一部分。

因此：

- 新工具不要只写一句说明，至少要写清用途、关键参数、常见用法
- 中小模型更依赖示例；复杂工具请给多条示例
- 如果是组合型能力，要在 prompt 或 workflow 里教模型如何串起来用
- 文档语气保持公开项目风格，不要写成面向单次对话的措辞

## Issue 与 PR 建议

提 issue 时，尽量提供：

- 运行环境：Windows / Linux、Python 版本
- 使用的客户端：Codex、Claude Code、LM Studio、OpenCode 等
- 触发的工具名
- 输入参数
- 实际返回
- 期望结果
- 复现步骤

提 PR 时，尽量写清：

- 改了什么
- 为什么改
- 是否影响工具行为或返回结构
- 补了哪些测试
- 是否更新了 README / docs / descriptions

## 兼容性优先级

这个项目当前更看重：

1. 工具真实可用
2. Windows / Linux 行为尽量一致
3. 返回结构稳定
4. 依赖尽量少而稳
5. 文档和提示词能教会模型使用

如果一个改动能增加“功能数量”，但会明显损害其中任何一项，通常不值得合并。
