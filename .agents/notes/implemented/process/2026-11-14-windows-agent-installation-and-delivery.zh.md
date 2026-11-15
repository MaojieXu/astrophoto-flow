# Agent Note: Windows agent 安装与评审后交付

Status: implemented

[English](2026-11-14-windows-agent-installation-and-delivery.md) | 中文

## Problem

agent（智能体）需要安装本地工作台、连接 MCP、请求启动并返回可用的浏览器地址。仅有依赖说明的检出不提供这条路径。此前的[不做分发提案](../../rejected/simplification/2026-11-14-no-distribution-engineering.zh.md)避免了单人开发检出的维护成本，但所需的 agent 安装需要版本化归档、安装器与发行检查。

纯 HTTP MCP 无法在没有已运行控制守护进程时冷启动已停止的服务。仅为引导增加一个永久服务会增加生命周期负担。替代方案需要范围严格受限的本机执行路径。

## Decision

交付脚本面向 Windows x64。GitHub Releases 承载 ZIP、对应源码、安装器、清单、校验值与原生验证报告；npm 承载编译后的 MCP 包。根包版本是权威。开发 tag 使用 `X.Y.Z-dev.N` 与 npm `next`。fork 版本独立，不包含 WSL 发行产物或配置。

PowerShell 安装器管理应用目录内的 uv、Python 和 Node，根据锁文件安装后端并安装精确的 MCP tarball。部分下载与包缓存可供重试复用。代码先解压到版本目录，再在其中创建虚拟环境，因此不移动已安装依赖的环境。工作区数据单独存放并保留。失败安装不改变生效收据；存在运行工作区记录时，不自动跨版本切换。

npm 包暴露 `workbench_init`、`workbench_start`、`workbench_status` 与 `workbench_stop`，以及通过 HTTP 提供的节点查询。只有 `src/mcp/src/lifecycle/bootstrap.ts` 导入进程创建能力。它启动固定的 `installer/install.ps1` 与已安装控制器的 CLI，可执行文件和参数来自固定的产品版本、安装收据及固定控制器入口，不来自工具参数。安装在一个 detached 的 Node worker 中运行，由该 worker 持有 PowerShell 控制台：直接 detached 时 Windows PowerShell 5.1 可能在 `-File` 执行前以 0 退出，而 worker 让安装器在 MCP 断开后继续存活，同时不增加命令或脚本入口。启动器输出与安装器自己的日志是不同文件，避免追加写日志同时充当进程 stderr。安装器按运行时平台而非被过滤的 `OS` 环境变量判断 Windows x64，仅在确认目标目录归属后才写回执，并通过操作文件暴露进度，由 `workbench_status` 以 `installing` 轮询。控制器在一份实现中拥有子进程身份、启动与停止，并与类型化的 FastAPI 生命周期路由共享。MCP 在返回回环地址前核对记录的版本与工作区身份、服务健康和 HTML 端点。未知状态阻止盲目重试启动。

tag 构建在生成草稿前验证源码前提、构建前端与 MCP、组装产物并执行原生 Windows 验证。人工发布复用这些字节，检查版本、提交、校验值与完整验证报告，先发布 npm，再公开 GitHub。已有 npm 版本必须匹配 tarball 完整性。OIDC 发布与仓库可见性由维护者准备，不是安装器动作。

## Alternatives considered

**继续仅从检出分发。** 对本需求否决：它让每个 agent 重新推导工具链准备与启动。旧提案保留为防止引入无关打包设施的约束。

**恢复 Python wheel 与 npm Python 引导。** 否决：归档已包含引擎源码树与构建页面。uv 在一个环境中安装依赖；npm 不安装或内嵌 Python 应用。

**以直接 detached 的 PowerShell 进程启动安装器。** 否决：在 `DETACHED_PROCESS` 下，Windows PowerShell 5.1 会在未执行 `-File` 的情况下以 0 退出；修改 `windowsHide` 或 `InputFormat` 无效，而非 detached 的子进程会随 Node 父进程一起结束。detached 的 Node worker 保持控制台归属，同时仍只运行固定的安装器脚本。

**安装永久引导服务以保持 MCP 纯 HTTP。** 否决：工作台启动前又多一个需要配置和维护的进程。单个固定启动适配器是显式例外，任意 shell 执行仍不可用。

**分发已安装的虚拟环境或 Windows 安装向导。** 否决：从固定平台 wheel 重建可以避免环境路径迁移问题，而 agent 已提供安装界面。

**发布时重建或 tag 后自动公开。** 否决：评审者必须批准通过验证的同一批字节。tag 产生草稿；公开发布需要独立人工操作。

## Consequences

干净机器仍需下载依赖；安装器保留缓存并校验固定的运行时归档。两个注册渠道不是事务：npm 成功而 GitHub 失败时，检查 npm 完整性一致后重试 GitHub 发布。首次 scope 所有权与 trusted publisher 配置仍是外部前提。

MCP 构建与评审 tarball 是可执行打包路径。原生 PowerShell 失败场景验证了校验值拒绝、归档路径逃逸拒绝，以及不激活缺少控制器的载荷。限定范围的边界覆盖检查启动例外，同时不放开后端导入。Windows 候选包增加一次真实 MCP、安装器、控制器、服务与引擎的端到端执行；install、init、start、节点查询、stop 与再 start 通过其 30 项平台检查。

控制器位于 `src/workbench/backend/astrophotoflow`，安装器用 uv 安装它，预检因此不再报告控制器文件缺失。候选构建声明 `publication: candidate` 与 `publishable: false`：通过验证的候选包来自有未提交改动的工作区，不能发布。通过的检查仍未触及浏览器，所以渲染、画布交互与 JavaScript 错误仍未验证；忙碌队列或正在校验 prompt 时拒绝 stop、并发安装、安装器异常退出的恢复、以及从公开 GitHub Release 或 npm 首次安装同样未验证，本轮使用的是本地候选 manifest。加入这些脚本不执行打 tag、npm 发布、GitHub 发行或仓库可见性变更。

## Related

拟议的[单一 MCP 安装与控制流程](../../proposed/feature/2026-11-14-mcp-install-start-stop-workbench.zh.md)维护本记录所报告的生命周期范围：MCP 优先的安装顺序、stop 权限，以及对繁忙或未知进程状态的拒绝。因其验收标准尚未端到端验证，该提案仍保持 proposed。本记录陈述已发布行为，并保留产物验证与评审后发布的理由；候选包通过不能证明提案中未验证的分支成立。
