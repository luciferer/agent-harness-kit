# Agent Harness Kit

一个可移植的代理协作模板与轻量证据校验器。它描述“主代理控制目标与授权、执行器只做有限任务、执行回执与独立验收分开”的工作方式。它**不是**多供应商调度引擎：不会发现或调用代理、Skills、MCP、模型、API 或 CLI，也不会自动执行任务包中的命令。

## 快速开始

要求 Python 3.11 或更新版本；工具仅使用 Python 标准库。

```sh
python3.11 harness.py validate-task examples/task.synthetic.json
python3.11 harness.py validate-receipt examples/receipt.pending.synthetic.json --task examples/task.synthetic.json
python3.11 -m unittest discover -s tests -v
```

第二条示例会显示执行器报告 `completed`，但主代理尚未验收，因此结果是 `reported_completed_pending_acceptance`，不代表通过。要形成已验收结果，主代理应在独立验收记录中给出结论、每项通过检查及对应证据；执行器的自我报告不能替代这一步。

## 使用方式

1. 复制 [`templates/AGENTS.template.md`](templates/AGENTS.template.md) 到自己的项目说明文件，并按项目权限和风险收窄内容。
2. 为具体工作填写 [`templates/task-packet.md`](templates/task-packet.md)，明确目标、目标身份、唯一写入者、可用接口、允许动作、禁止事项、证据和停止条件。
3. 执行器完成后填 [`templates/execution-receipt.md`](templates/execution-receipt.md)。使用 `completed` 只表示执行器报告其工作完成。
4. 主代理依据 [`templates/independent-acceptance.md`](templates/independent-acceptance.md) 复核目标状态并记录 accepted、rejected 或 pending。
5. 用 `harness.py validate-receipt RECEIPT --task TASK` 校验任务 ID 和验收状态。

## 状态语义

- `reported_status`: 执行器报告 `completed`、`partial`、`failed` 或 `blocked`。
- `independent_acceptance.status`: 主代理记录 `pending`、`accepted` 或 `rejected`。
- 校验器只在执行器报告完成、主代理明确接受、验收者与执行者不同、每项验收检查均通过且有证据时输出 `accepted`。它不判断证据真假，也不执行被验收的动作。
- 缺失验收、检查未做、证据为空或状态矛盾都不会被升级为通过。
- 校验器只读取命令行指定的 JSON 文件，每份最多 1 MiB；不会执行任务内容。结构错误返回退出码 2，结构正确但仍待验收的回执返回退出码 0，并明确报告 `reported_completed_pending_acceptance`。

## Skills 与 MCP 示例

[`examples/skill-interface.example.md`](examples/skill-interface.example.md) 与 [`examples/mcp-config.example.toml`](examples/mcp-config.example.toml) 仅展示占位结构。MCP 示例默认禁用，名称与命令均为假名；不会连接 provider 或启动工具。安装、授权和凭据配置需由使用者在目标客户端按其官方流程完成。存在 Skill 文件或 MCP 配置不证明当前代理能发现、获准或成功调用它。

## 文件内容与隐私

样例任务、回执和接口名均为合成内容。不要把提示词、工具参数/结果、凭据、私有日志或不必要的个人路径粘贴到公开 issue、回执或样例中。证据可使用脱敏的相对路径、摘要或可读回的状态描述；不要仅凭退出码、HTTP 状态、窗口存在或执行器自报成功作验收。

`.gitignore` 排除运行日志、环境文件、常见凭据文件、Python 缓存和本地运行目录。项目代码与模板采用 [MIT License](LICENSE)。

## 交流社区

[LINUX DO](https://linux.do/)：感谢社区提供开源项目交流与反馈的空间。项目使用问题和改进建议也可通过本仓库 Issues 反馈。
