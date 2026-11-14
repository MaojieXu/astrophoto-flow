# Agent Note: MCP 是任务客户端，不是第二个后端

Status: proposed

[English](2026-11-14-node-mcp-for-the-tool-surface.md) | 中文

## Problem

旧 MCP 服务器暴露了 126 个工具，它们与 CLI 从同一份服务目录生成。它的领域操作已经是 HTTP 调用，但进程还读取工作区配置、服务令牌和进程文件，并且能启动工作台。这种形态鼓励了两个错误：把每条 HTTP 路由都当成 agent 工具，以及让 MCP 进程变成第二个知道如何写素材库的地方。新仓库需要一个小型、任务形态的表面，帮助 agent 查找图像、准备导入、组装图并读取回执，同时不给它数据库句柄、停止按钮或领域的第二份实现。

## Proposal

MCP 服务器是一个 Node 进程，通过 HTTP 与工作台服务通信。它不拥有数据库、SQLite 文件或素材库写入路径。它暴露大约十五个任务工具，而不是每条路由一个工具。

### 运行时与传输

服务器运行在与前端相同的 Node 线（`>=26.8.2 <27`）上，使用 stdio。它由 MCP 客户端启动，而不是由工作台启动。它读取两个本地东西：工作区路径（来自自身配置或环境变量）和派生路径 `data/service.token` 上的 bearer 令牌。它读取 `run/processes.json` 以了解当前运行的实际服务和引擎端口；它永远不打开 SQLite 数据库。

令牌是唯一的秘密。它永远不会被记录、不会出现在工具结果里，也不会作为工具参数被接受。

### 工具

表面按 agent 正在做的任务分组：

- **查找**：`assets_find`、`assets_get`、`datasets_find`、`datasets_get`、`calibration_find`、`nodes_find`、`nodes_get`。结果带稳定 id、紧凑事实和游标；它们不会倾倒整张表。
- **准备导入**：`imports_inspect`、`imports_preflight`、`imports_submit`。检查和预检是只读的并返回 `review_token`；提交需要该令牌和调用方提供的 `request_id`。
- **观察任务**：`tasks_status`、`tasks_wait`。两者接受任务 id 或请求 id，并返回逐阶段进度，而不是原始日志。
- **组装图**：`canvas_get`、`canvas_add_data`、`canvas_edit`。它们需要页面 id、工作流 id、图 id 和内容令牌；编辑工具还需要 `operation_id`。
- **读取结果**：`receipts_get`。回执按 `operation_id` 或 `request_id` 寻址，包含结果、受影响的 id 和错误。
- **工作台**：`workbench_status`、`workbench_start`。服务停止时状态仍然可用。启动会准备并启动工作台；它是唯一暴露的生命周期操作。

没有 `stop`、没有 `restart`、没有设置写入、没有数据库查询、没有任意文件读取、没有 shell 工具。

### 契约与错误

服务的 OpenAPI 文档是 schema 来源。签入的快照和生成器产生 MCP 校验器；当快照与运行中的服务不一致时，契约测试失败。只有在生成器无法表达约束的地方才允许手写 Zod schema，而那些 schema 仍然参与漂移检查。

每个业务工具都带请求 id 调用 HTTP API。服务错误变成结构化工具错误，包含服务代码、消息、字段路径和请求 id。服务停止返回 `WORKBENCH_NOT_RUNNING`，并提示调用 `workbench_start`；它不会自动启动。超时返回 `TRANSPORT_TIMEOUT`；连接失败返回 `SERVICE_UNAVAILABLE`。未知结果按同一个 `operation_id` 或 `request_id` 查询，永远不用新 id 重试。

### 保留在本地的部分

MCP 进程可以读取配置以找到工作区，可以读取进程文件以找到实际端口。它可以通过本地控制器启动工作台。它不能写配置、停止进程、重启进程或直接编辑素材库。如果未来工具需要本地操作，它走服务或控制器，而不是私有代码路径。

本地参考语料是一个独立的只读模块，不是另一条领域路径；[它的笔记](../feature/2026-11-14-agent-knowledge-base-rag.zh.md)规定了 agent 如何检索并引用它。

### CLI

CLI 仍然是人类与运维表面。它调用同一 HTTP API 和同一控制器；它不是每个工具生成一条命令，也不是 MCP 目录的来源。需要任务工作流的脚本可以使用 CLI，但 MCP 工具列表是 agent 契约。

## Alternatives considered

**保留 Python MCP 服务器并裁剪目录。** 否决：它会保留一个带自己依赖集、自己一份配置/令牌逻辑的第二个 Python 进程。前端已经运行 Node，一个小型 HTTP 客户端更容易保持诚实。

**把每条服务路由暴露成工具。** 否决：60 多条路由会产生 agent 无法选择的目录，而且很多路由是 UI 管道（分页令牌、预览租约、目录选择器）。任务工具把那些路由组合在一个意图后面。

**让 MCP 直接读 SQLite。** 否决：它会绕过修订检查、值来源和单写者规则，schema 变更会悄悄破坏 agent。HTTP 是唯一的领域路径。

**在第一次业务调用时自动启动工作台。** 否决：只读查询不应该启动两个进程，而工具调用中途的启动失败很难解释。`workbench_start` 是显式的。

**为了对称暴露 stop 和 restart。** 否决：外部 agent 不应该关掉人类正在使用的工作台。停止和重启留在 CLI 与网页表面。

**像以前那样为每个工具生成 CLI 命令。** 否决：它复制目录，而且生成的命令只是同一批 HTTP 调用的薄包装。CLI 可以只暴露人类真正会脚本化的少数操作。

## Acceptance criteria

- MCP 服务器不打开 SQLite 数据库，也不包含素材库写入路径。
- 工具列表是任务形态的，不包含 stop、restart、设置写入、任意文件或 shell 工具。
- 服务停止时业务工具返回 `WORKBENCH_NOT_RUNNING`；`workbench_start` 是唯一的自动启动路径。
- 令牌从派生路径读取，永不记录，也永不作为工具参数接受。
- 当签入的 schema 快照与运行中的服务不一致时，契约测试失败。
- 错误保留服务代码、消息、字段路径和请求 id。
- 未知结果按同一个操作或请求 id 查询，不用新 id 重试。
- 服务停止时 `workbench_status` 仍然可用，并报告受管理、未确认、已退出和未管理状态。
- 服务器在前端的 Node 线上通过 stdio 运行。

## Risks

- 契约漂移是主要失败模式。快照测试能抓住 schema 变更，但它必须与服务测试在同一个门禁里运行，否则 MCP 会悄悄落后。
- 从 MCP 工具启动工作台可能与人类启动竞争。控制器的身份和就绪检查必须让第二次启动变成复用或明确拒绝，而不是重复启动。
- 权限错误的令牌文件是安全缺陷。服务器应该拒绝读取非仅所有者可读的令牌，而不是继续。
- 任务工具仍可能长成路由代理。每个新工具需要命名的任务和验收标准，而不是与端点一一对应。
- Node 26 比许多 MCP 客户端假设的更新；包必须声明 engine，并在旧运行时上给出清晰失败。
