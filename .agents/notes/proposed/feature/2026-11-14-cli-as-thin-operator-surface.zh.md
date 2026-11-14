# Agent Note: CLI 是轻量运维表面，不是第二个 API

Status: proposed

[English](2026-11-14-cli-as-thin-operator-surface.md) | 中文

## Problem

旧 CLI 有两半：手写的本地应用负责工作区与进程操作，生成的业务应用每个 MCP 工具一条命令。生成的那一半复制目录，产生 126 条命令，并在工具变化时漂移。新仓库仍然需要可脚本化的路径来初始化、启停、诊断和少量素材库任务，但它不需要领域的第二份实现，也不需要每条路由一条命令。

## Proposal

CLI 是同一 HTTP API 和同一本地控制器上的轻量客户端。它有一小组任务形态的命令、稳定的 JSON 输出和文档化的退出码。

### 入口与工作区

CLI 以 `python -m astrophotoflow.cli` 从与服务相同的环境运行；它不作为 console script 安装。工作区来自 `--workspace` 或 `ASTROPHOTOFLOW_CONFIG`，与服务完全一致。每个与运行中工作台通信的命令都从派生路径读取令牌，并拒绝非仅所有者可读的令牌。

### 本地命令

`init` 创建工作区，带严格的默认 `config.toml` 和目录布局。`status` 把服务和引擎报告为受管理、未确认、已退出或未管理，并报告已保存和生效端口。`start` 和 `stop` 驱动控制器；`restart` 返回操作 id，并可按 id 查询。`doctor` 运行本地检查，每项检查打印一行。`mcp-config` 打印可直接粘贴的 MCP 客户端条目，包含工作区路径和 Node 服务器命令；它不编辑用户的客户端配置。

`config get` 打印已保存配置和生效运行时值。`config set` 只接受设置 API 接受的键，保留文件其余部分，并报告 `restart_required`；它永远不重启。`language get|set` 使用与网页 UI 相同的 `Comfy.Locale` 路径。

### 领域命令

领域命令按任务分组，而不是按路由：`library search`、`library show`、`library import`、`dataset show`、`dataset members`、`calibration check`、`task status`、`task wait`、`graph show` 和 `receipt show`。每个接受 id 或请求 id，默认打印紧凑表格，`--json` 打印完整响应。

CLI 不暴露安装、卸载或 bundle 准备；那些需要原生网页确认。它暴露只读的 bundle 目录。它不暴露直接 SQLite 访问、任意 HTTP 路径，或绕过任务 schema 的通用 `call` 命令。

### 输出与错误

`--json` 向 stdout 打印一个 JSON 对象，字段与 HTTP 响应相同，包括请求 id。人类输出到 stdout；诊断到 stderr。成功命令退出 0；用法错误退出 2；冲突退出 3；服务不可用退出 4；结果未知退出 5；内部错误退出 1。精确代码也出现在 JSON 错误信封里。

CLI 永远不为破坏性操作做交互式提示。`library trash purge` 需要显式 `--fingerprint` 和 `--yes`；`stop` 不需要确认，但会拒绝未验证的进程。因此脚本可以非交互地运行每条命令。

### 与 MCP 的关系

CLI 和 MCP 调用同一批 HTTP 端点，但职责不同。MCP 是 agent 表面，返回结构化工具结果；CLI 是人类与脚本表面，提供表格、退出码和本地生命周期命令。两者都不拥有私有领域路径，也不从对方生成。

## Alternatives considered

**像以前那样为每个 MCP 工具生成一条命令。** 否决：它复制目录，让每次工具改名都成为 CLI 破坏性变更，并产生只是 HTTP 调用外面一层参数解析的命令。任务形态的命令更少也更稳定。

**只保留 CLI，去掉 MCP。** 否决：agent 需要结构化工具 schema，而不是 shell 解析。两个表面共享 API，不共享展示。

**让 CLI 在进程内导入 Python 服务。** 否决：它会绕过单写者 HTTP 边界，让 CLI 成为打开数据库的第二个进程。即使在同一台机器上，CLI 也是客户端。

**把生命周期命令只放在 MCP 后面。** 否决：人类操作员需要 `start`、`stop` 和 `doctor`，而不需要 agent；MCP 服务器也不应该是恢复已停止工作台的唯一方式。

**保留通用 `call <tool> --json` 逃生口。** 否决：它在另一个名字下重建生成目录，并给脚本一条契约测试覆盖不到的弱类型路径。

## Acceptance criteria

- CLI 从与服务相同的环境运行，并以相同方式解析工作区。
- 本地命令覆盖 init、status、start、stop、restart、doctor、mcp-config、config get/set 和 language get/set。
- 领域命令是任务形态的，不包含通用 call 命令。
- `--json` 返回与 HTTP 响应相同的字段，包括请求 id。
- 退出码区分成功、用法、冲突、不可用、未知和内部错误。
- 破坏性命令非交互，并要求显式指纹。
- CLI 从派生路径读取令牌，并拒绝非仅所有者可读的令牌。
- CLI 不打开 SQLite，也不直接写素材库。

## Risks

- 小命令集仍可能偏离 API。每条命令需要针对 MCP 使用的同一 schema 快照做契约测试。
- JSON 输出是脚本接口；改变字段就是破坏性变更。note 应点名稳定字段，并随 API 版本化。
- 未知结果的退出码 5 容易与一般失败混淆；JSON 信封必须携带精确状态。
- 如果 `config set` 重写文件，可能丢失注释。首版应保留注释，或说明不保留。
- CLI 没有安装，所以每次调用都需要环境和模块路径。README 必须给出受支持平台的确切命令。
