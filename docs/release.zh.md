# Windows 交付

[English](release.md) | 中文

Windows x64 交付流程把工作台打包给 agent（智能体）安装，再通过 npm MCP 包暴露启动与状态能力。GitHub Releases 承载工作台产物；npm 承载 `@xu016/astrophoto-flow`。[发行组装器](../scripts/release/package.py)强制检查源码与运行时前提。

## 版本与产物

根 `package.json` 拥有产品版本。`vX.Y.Z-dev.N` tag 产生开发发行并使用 npm 的 `next` 标签；稳定版本使用 `latest`。fork 版本独立。MCP 构建在输出中记录产品版本，发行打包器在暂存目录提供公开 npm 元数据。源码 MCP 包保持私有，防止被直接发布。

每个草稿包含 Windows ZIP、匹配的源码归档、`install.ps1`、MCP tarball、`release-manifest.json`、`SHA256SUMS` 与 Windows 验证报告。ZIP 包含后端源码、锁定依赖、已构建前端与许可证，不包含虚拟环境、用户文件、模型权重和前端构建依赖。运行时下载固定在 [runtime.json](../scripts/release/runtime.json) 中。

## 本地入口

从仓库根目录运行：

```sh
pnpm release:preflight
pnpm --filter @xu016/astrophoto-flow build
python scripts/release/package.py --mcp-only --output .artifacts/mcp-review
```

预检拒绝缺少控制器文件、版本不符和工作区未提交的情况。仅 MCP 命令产生评审用 tarball，不是已验证的工作台发行。Windows 构建入口是 `scripts/release/build.ps1`；它要求干净的已打 tag 检出，在组装产物前构建前端与 MCP。配套的 `scripts/release/verify.ps1` 安装到临时工作区，并产生发布必需的报告。

## Agent 安装与启动

安装器接受 `-Version`、`-InstallRoot` 和 `-Workspace`，默认使用 `%LOCALAPPDATA%\AstroPhotoFlow`，拒绝非空且不属于自身的目录，使用独立的版本、运行时和缓存目录，并通过 uv 安装 Python 依赖。工作区位于可替换的版本目录之外。下载保留部分文件以支持续传，并检查 SHA-256。已安装依赖的 Python 环境保留在最终路径。

安装器输出一个 JSON 结果，包含安装路径、生效版本、`restart_required`，以及 MCP 连接的 `command` 和 `args`。日志使用 stderr。候选版本验证提供本地 `-ManifestPath`；正常安装获取已发布版本及匹配的 npm 包。重装保留工作区内容。存在进程记录时，准备另一版本会保留当前生效版本，并报告需要重启。

stdio MCP 入口接受 `--install-root` 和 `--workspace`。只有 `workbench_start` 可以启动固定控制器；状态和后续业务工具不接受可执行命令。启动结果暴露已核实的回环 `web_url`、选定版本与工作区，以及是否复用实例。结果未知时必须先调查，再决定是否再次启动。

## 控制器契约

后端提供 `python -m astrophotoflow.cli init|start|stop --workspace <path> --json`。Init 保留已有配置。Start 在创建子进程前持久保存 `run/processes.json`；只有健康检查通过后，其 `client` 对象才变为就绪。Stop 检查进程身份、确认停止，并移除已停止的记录。未知记录保留供调查。

就绪对象包含 `status: "ready"`、`version`、`workspace`、`service_url`、`web_url` 与 `reused`。Start 把该对象输出到 stdout，诊断写到 stderr。服务 `GET /health` 返回 `status: "ok"`、`version` 与 `workspace`。部署的产品版本与提交来自生成的 `astrophotoflow/release-version.json`，不来自引擎项目版本。MCP 同时检查实时身份与 HTML 端点。引擎必须显式提供打包的 `web` 目录，不使用 pip 安装的前端。知识库索引缺失不阻塞画布。

## 草稿与公开发布

tag workflow 从 `main` 上的提交构建，验证干净 Windows 安装后创建草稿。验证覆盖路径空格、中断下载、校验失败、工作区内容保留、默认端口被占用、重复启动，以及 MCP 断开后网页仍存活。报告把所有产物哈希绑定到版本与提交。缺少入口或验证失败会阻止草稿产生。

人工触发的 `publish.yml` workflow 校验已有草稿产物，不重新构建。它通过 npm OIDC 发布精确的 MCP tarball，再公开 GitHub Release。已有 npm 版本仅在完整性一致时复用。npm 发布失败会保留 GitHub 草稿。首次公开发行要求维护者公开对应源码仓库，并建立 npm scope 所有权与 trusted publisher；workflow 不修改仓库可见性。

[交付决策](../.agents/notes/implemented/process/2026-11-14-windows-agent-installation-and-delivery.zh.md)记录取舍与验证限制。首版交付不支持 WSL 发行。
