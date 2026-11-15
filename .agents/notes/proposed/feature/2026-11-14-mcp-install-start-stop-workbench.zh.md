# Agent Note: 一个 MCP 安装并控制工作台

Status: proposed

[English](2026-11-14-mcp-install-start-stop-workbench.md) | 中文

## Problem

agent（智能体）必须通过 workbench_init 下载并初始化工作台，通过 workbench_start 启动，通过 workbench_stop 停止。要求 MCP 连接前已有安装收据，或者让安装器在工作台之后安装 MCP，都颠倒了所需流程。当前不允许 stop 的限制也阻止了所需生命周期。

## Proposal

一个 TypeScript FastMCP TS 服务器拥有用户可见的生命周期工具。宿主提供 Node；npm 包携带固定的 PowerShell 安装 worker。Init 下载匹配的已发布工作台，准备 uv、Python、锁定依赖与工作区。它返回持久安装操作，status 观察完成情况。Worker 不安装第二个 MCP，也不为正在运行的 Node 宿主下载替代品。

Start 与 stop 调用固定的已安装 Python 控制器。控制器与类型化的 FastAPI 生命周期路由共享真实实现，拥有进程身份、并发、就绪和停止。FastAPI 通过 HTTPX 注册原生节点查询；业务工具调用这些 HTTP 接口。原生编辑器保留图保存、撤销与执行。

安装与运行状态分别维护。重复初始化保留工作区数据；重复 start 复用实例；stop 保留安装与数据，并让 MCP 保持连接。繁忙或身份未知时拒绝操作，不强制处理。只有生命周期引导适配器可创建固定安装器或控制器进程；工具不接受任意命令、URL 或 PID。

Windows 候选包验证真实的 MCP → init → start → 节点查询 → stop → start 顺序。候选快照可在本地安装，不能公开发布。正式发行保留干净的已打 tag 源码、产物校验值、Windows 原生验证和同一批字节的人工发布。

### 范围与相关记录

本提案接管[任务客户端提案](../architecture/2026-11-14-node-mcp-for-the-tool-surface.zh.md)中扩展的生命周期，取代其外部安装、仅启动和禁止停止的限制。业务 HTTP 边界、生成契约与禁止执行整图的规则仍然有效。原生图归属仍由[画布提案](../architecture/2026-11-14-native-canvas-and-service-receipts.zh.md)维护。

[已实现的交付记录](../../implemented/process/2026-11-14-windows-agent-installation-and-delivery.zh.md)描述安装器、已发布的生命周期工具与验证证据。本提案维护生命周期范围与验收；候选包通过不能证明其未完成分支成立。该记录的校验值、产物身份与评审后发布理由仍然有效。

### 当前实现状态

本生命周期的一部分已在 Windows x64 发布。已发布：npm 包中的 `workbench_init`、`workbench_start`、`workbench_status` 与 `workbench_stop`；位于固定 detached Node worker 之后的 PowerShell 安装器；拥有进程身份、启动与停止的 Python 控制器；通过 HTTP 的节点查询；以及一个本地候选包，用真实 MCP、安装器、控制器、服务与引擎跑通 install、init、start、节点查询、stop 与再 start。

未验证：浏览器渲染、画布交互与 JavaScript 错误；忙碌队列或正在校验 prompt 时拒绝 stop；并发安装与安装器异常退出的恢复；以及从公开 GitHub Release 或 npm 首次安装——本轮使用的是本地候选 manifest。该候选包为 `publishable: false`，未执行打 tag、npm 发布、GitHub 发行或仓库可见性变更。这些未完成分支是本记录仍为 proposed 而非 implemented 的原因。

实现阶段覆盖 Windows x64 的生命周期控制与原生节点查询，使用现有 uv/Python 3.12 环境及已声明的 FastAPI、Pydantic、SQLAlchemy、Alembic、HTTPX 和 psutil 依赖。素材管理、校准、bundle、远程画布编辑、检索与 benchmark 实现仍是独立能力。现有前端与原生执行引擎继续复用。

## Alternatives considered

**在 MCP 之前安装工作台。** 否决：init 必须通过已经连接的 MCP 完成下载与初始化。

**要求每个生命周期调用都经过 FastAPI。** 否决：未安装或已停止的服务不能安装或冷启动自身。固定本机适配器处理这些操作；业务查询保持为 HTTP。

**继续不向 MCP 提供 stop。** 被明确的生命周期需求否决。范围与进程身份把工具限制在配置的工作区。

**把 init 保持为无界阻塞的单次工具调用。** 否决：运行时与依赖下载可能超过客户端请求超时。持久安装操作让进度和中断结果可观察。

## Acceptance criteria

- 一个 MCP 能在工作台未安装时连接，并完成 init、start 和 stop。
- Init 下载并初始化真实软件；status 区分受理与完成，允许中断重试而不丢失数据。
- Start 返回已核实的原生网页地址；节点查询通过 FastAPI 返回真实引擎目录。
- Stop 只影响核实归属的进程，保留工作区内容，并让 MCP 能再次 start。
- 本地 Windows 候选包通过同样有意义的安装与生命周期检查；公开发布器拒绝候选包或不完整报告。

## Risks

宿主必须先提供支持的 Node 运行时，才能运行 MCP。干净机器的安装需要网络。临时安装 worker 与服务停止需要持久状态来区分失败和未知结果。必须一起修改现有安装器、收据、生命周期权限和验证顺序；只修改工具名称无法消除引导循环。
