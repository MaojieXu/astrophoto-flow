# Agent Note: MCP 是任务客户端，不是第二个后端

Status: proposed

[English](2026-11-14-node-mcp-for-the-tool-surface.md) | 中文

## Problem

旧 MCP 服务器暴露了 126 个工具，它们与 CLI 从同一份服务目录生成。它的领域操作已经是 HTTP 调用，但进程还读取工作区配置、服务令牌和进程文件，并且能启动工作台。这种形态鼓励了两个错误：把每条 HTTP 路由都当成 agent 工具，以及让 MCP 进程变成第二个知道如何写素材库的地方。新仓库需要一个小型、任务形态的表面，帮助 agent 查找图像、准备导入、组装图并读取回执，同时不给它数据库句柄、不受限的进程控制或领域的第二份实现。

## Proposal

MCP 服务器在 Node 包 `src/mcp` 中使用 `@prefecthq/fastmcp-ts` 和 Zod 4，通过根 pnpm workspace 安装。Node HTTP 客户端调用工作台 API。FastMCP TS 负责工具注册、校验与 stdio；该包不持有数据库、SQLite 文件、检索引擎或素材库写入路径。工具目录按任务组织，而不是每条路由一个工具。

[单一 MCP 安装与控制提案](../feature/2026-11-14-mcp-install-start-stop-workbench.zh.md)维护生命周期安装、启动与停止。它部分取代本记录原先的外部安装、仅启动生命周期和禁止停止的策略；下文业务目录与 HTTP 归属仍然有效。

### 运行时与传输

服务器运行在与前端相同的 Node 线（`>=26.8.2 <27`）上，使用 stdio。它由 MCP 客户端启动，而不是由工作台启动。连接参数选择安装根目录与工作区，并提供 Windows 默认值。连接不要求已有安装收据：init 创建它，status 区分安装进度与运行状态，start 在初始化后检查实时身份。业务客户端从配置的数据目录下派生的 `service.token` 路径读取 bearer 令牌。MCP 从不打开 SQLite 数据库。

令牌是唯一的秘密。它永远不会被记录、不会出现在工具结果里，也不会作为工具参数被接受。

### 工具

表面按 agent 正在做的任务分组：

- **查找**：`assets_find`、`assets_get`、`datasets_find`、`datasets_get`、`calibration_find`、`nodes_find`、`nodes_get`。结果带稳定 id、紧凑事实和游标；它们不会倾倒整张表。
- **准备导入**：`imports_inspect`、`imports_preflight`、`imports_submit`。检查和预检是只读的并返回 `review_token`；提交需要该令牌和调用方提供的 `request_id`。
- **观察任务**：`tasks_status`、`tasks_wait`。两者接受任务 id 或请求 id，并返回逐阶段进度，而不是原始日志。
- **组装图**：`canvas_get`、`canvas_add_data`、`canvas_edit`。它们需要页面 id、工作流 id、图 id 和内容标记；编辑工具还需要 `operation_id`。[原生页面桥接](2026-11-14-native-canvas-and-service-receipts.zh.md)应用编辑并保留原生保存与撤销；这些工具不提交整图执行。
- **读取结果**：`receipts_get`。回执按 `operation_id` 或 `request_id` 寻址，包含结果、受影响的 id 和错误。
- **工作台**：`workbench_init`、`workbench_start`、`workbench_stop`、`workbench_status`。Init 通过固定安装 worker 下载并初始化匹配的工作台；status 观察其持久结果与运行状态。Start 启动或复用已初始化工作台，返回已核实的 `web_url`。Stop 只终止已核实归属的工作区进程，保留安装与数据。并发、繁忙拒绝与未知结果归生命周期提案维护。

没有 `restart`、任意设置写入、数据库查询、任意文件读取或 shell 工具。Init 与 stop 是显式且限定范围的生命周期能力，不是通用进程或文件系统工具。

### 契约与错误

FastAPI 服务的 OpenAPI 文档是 schema 来源。签入的快照和 `@hey-api/openapi-ts` 为独立的前端与 MCP 消费方生成 TypeScript 客户端和 Zod 校验器；MCP 从不导入 UI 包。快照与运行中服务不一致时，契约测试失败。只有生成器无法表达约束时才允许手写 Zod schema，这些 schema 仍参与漂移检查。

每个业务工具都带请求 id 调用 HTTP API。服务错误变成结构化工具错误，包含服务代码、消息、字段路径和请求 id。服务停止返回 `WORKBENCH_NOT_RUNNING`，并提示调用 `workbench_start`；它不会自动启动。超时返回 `TRANSPORT_TIMEOUT`；连接失败返回 `SERVICE_UNAVAILABLE`。未知结果按同一个 `operation_id` 或 `request_id` 查询，永远不用新 id 重试。

### 保留在本地的部分

只有固定生命周期引导适配器可启动包内 PowerShell 安装 worker，或以固定控制器动作调用已安装的 uv 可执行文件。Init 必须在 Python 或业务服务不存在时可用。适配器不从工具参数接受可执行文件、脚本、URL 或 PID，也不导入后端模块。Python 控制器拥有进程身份、并发、就绪与停止；业务工具使用 HTTP。安装可以创建新的工作区配置，但必须保留已有配置与数据。这是对[当前交付实现](../../implemented/process/2026-11-14-windows-agent-installation-and-delivery.zh.md)的拟扩展，不表示现有安装器或启动适配器已经提供 init 和 stop。

本地参考语料是一个独立的只读模块，不是另一条领域路径；[它的笔记](../feature/2026-11-14-agent-knowledge-base-rag.zh.md)规定了 agent 如何检索并引用它。

### CLI

CLI 仍然是人类与运维表面。它调用同一 HTTP API 和同一控制器；它不是每个工具生成一条命令，也不是 MCP 目录的来源。需要任务工作流的脚本可以使用 CLI，但 MCP 工具列表是 agent 契约。

## Alternatives considered

**保留 Python MCP 服务器并裁剪目录。** 否决：它会保留一个带自己依赖集、自己一份配置/令牌逻辑的第二个 Python 进程。前端已经运行 Node，一个小型 HTTP 客户端更容易保持诚实。

**把每条服务路由暴露成工具。** 否决：60 多条路由会产生 agent 无法选择的目录，而且很多路由是 UI 管道（分页令牌、预览租约、目录选择器）。任务工具把那些路由组合在一个意图后面。

**让 MCP 直接读 SQLite。** 否决：它会绕过修订检查、值来源和单写者规则，schema 变更会悄悄破坏 agent。HTTP 是唯一的领域路径。

**在第一次业务调用时自动启动工作台。** 否决：只读查询不应该启动两个进程，而工具调用中途的启动失败很难解释。`workbench_start` 是显式的。

**为了对称暴露 stop 和 restart。** 原提案为避免 agent 关闭人类工作台而拒绝两者。如今明确的 init/start/stop 需求通过[限定范围的生命周期提案](../feature/2026-11-14-mcp-install-start-stop-workbench.zh.md)取代禁止 stop 的限制；繁忙状态和进程身份检查继续保护不相关实例。Restart 仍不进入 MCP 目录。

**像以前那样为每个工具生成 CLI 命令。** 否决：它复制目录，而且生成的命令只是同一批 HTTP 调用的薄包装。CLI 可以只暴露人类真正会脚本化的少数操作。

## Acceptance criteria

- MCP 服务器不打开 SQLite 数据库，也不包含素材库写入路径。
- 工具列表是任务形态的，包含限定范围的 init/start/stop/status 生命周期，不包含 restart、任意设置写入、任意文件或 shell 工具。
- MCP 在安装前即可连接；init 下载并初始化一个工作台，不安装第二个 MCP；status 区分受理与完成。
- 服务停止时业务工具返回 `WORKBENCH_NOT_RUNNING`；`workbench_start` 是唯一的自动启动路径。
- 令牌从派生路径读取，永不记录，也永不作为工具参数接受。
- 当签入的 schema 快照与运行中的服务不一致时，契约测试失败。
- 错误保留服务代码、消息、字段路径和请求 id。
- 未知结果按同一个操作或请求 id 查询，不用新 id 重试。
- Stop 保留工作区，并让 MCP 仍可调用；再次 start 能返回已核实的网页。
- 服务停止时 `workbench_status` 仍然可用，并报告受管理、未确认、已退出和未管理状态。
- 服务器在前端的 Node 线上通过 stdio 运行。

## Risks

- 契约漂移是主要失败模式。快照测试能抓住 schema 变更，但它必须与服务测试在同一个门禁里运行，否则 MCP 会悄悄落后。
- 从 MCP 工具启动工作台可能与人类启动竞争。控制器的身份和就绪检查必须让第二次启动变成复用或明确拒绝，而不是重复启动。
- 权限错误的令牌文件是安全缺陷。服务器应该拒绝读取非仅所有者可读的令牌，而不是继续。
- 任务工具仍可能长成路由代理。每个新工具需要命名的任务和验收标准，而不是与端点一一对应。
- Node 26 比许多 MCP 客户端假设的更新；包必须声明 engine，并在旧运行时上给出清晰失败。
