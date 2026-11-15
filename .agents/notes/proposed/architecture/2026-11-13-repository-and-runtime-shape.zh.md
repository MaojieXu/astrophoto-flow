# Agent Note: 一个仓库，一个运行环境

Status: proposed

[English](2026-11-13-repository-and-runtime-shape.md) | 中文

## 问题

旧布局把产品切成三份：`src/astrophotoflow` 里的 Python 服务、`engine/` 下完整的 ComfyUI 副本、`frontend/` 下完整的 ComfyUI_frontend 副本，再用构建脚本和第二个运行期虚拟环境把它们接起来。切分的每一份代价都是维护：一个装着引擎归档的 wheel、一个 console script、一个持有运行期指纹的 bootstrap 工具、一份生成的 CLI，以及两个必须同步的环境。对"一个人在一台机器上运行"的产品，结构应该让人一眼回答两个问题：哪些代码是我的，哪个环境把它装起来。

## 提案

`src/` 下有三个运行目录：一个后端 uv 环境、一个前端 pnpm workspace，以及根 pnpm workspace 中的 MCP 包：

```text
src/workbench/backend/     # uv environment
    main.py, comfy/, nodes.py …     ComfyUI source
    astrophotoflow/                 our service package, importable without installing
    custom_nodes/astrophotoflow/    one registration file that points at the package
    web/                            frontend build output, git-ignored
    pyproject.toml, uv.lock
src/workbench/frontend/    # pnpm environment
    upstream source plus src/platform/astrophotoflow/
    packages/astrophotoflow-ui/     private business UI package
src/mcp/                   # root pnpm workspace, Node, HTTP plus fixed lifecycle actions
```

我们的包放在引擎树里，且从不安装：引擎从 `backend/` 起跑，`import astrophotoflow` 按目录位置解析，服务以 `python -m astrophotoflow` 启动。没有 wheel，没有 console script，没有运行期指纹。

目录名保留 `workbench`；产品名仍是 AstroPhotoFlow，这样改目录名永远不会改动产品叫什么。

引擎与 FastAPI 服务是同一个 Python 3.12 环境中的独立进程。ComfyUI 拥有图文件、草稿、保存、撤销、队列、进度与取消；服务拥有素材、数据集、命令准入与收据。HTTPX 调用引擎 aiohttp 桥接，WebSocket 把编辑送到原生页面，遵循[原生画布提案](2026-11-14-native-canvas-and-service-receipts.zh.md)。引擎崩溃不会连带关闭收据 API。

[知识库进程](../feature/2026-11-14-agent-knowledge-base-rag.zh.md)属于同一个 uv 环境，但仍是首期生命周期与节点查询实现之外的独立能力。它的代码归 `backend/astrophotoflow/knowledge/`，语料、索引与模型缓存使用独立数据目录。控制器拥有 Python 进程管理。MCP 业务工具保持为 HTTP 客户端；固定生命周期适配器遵循[安装与控制提案](../feature/2026-11-14-mcp-install-start-stop-workbench.zh.md)。两个 Node workspace 都使用 Node 26 与 pnpm 11.28.5。声明的依赖与安装方式见[开发参考](../../../../docs/development.zh.md)。

[agent 交付记录](../../implemented/process/2026-11-14-windows-agent-installation-and-delivery.zh.md)描述当前 Windows 归档与安装器，不使用 Python wheel 或内嵌虚拟环境。[单一 MCP 提案](../feature/2026-11-14-mcp-install-start-stop-workbench.zh.md)取代其中先工作台后 MCP 的预期安装顺序：宿主提供 Node 并先连接 MCP，init 安装工作台，start/stop 调用其控制器。前端 fork 继续[冻结](../simplification/2026-11-14-freeze-the-frontend-fork.zh.md)；业务工具保持为 [HTTP 客户端](2026-11-14-node-mcp-for-the-tool-surface.zh.md)。

## 数据归属

`backend/astrophotoflow/interfaces/http` 是唯一写入已登记素材、数据集或业务收据的入口。原生图持久化仍归 ComfyUI。以下边界必须明确：

- ComfyUI 上传路由拥有临时输入与输出，不登记素材库。图保存与撤销保持原生；科学输出登记经过业务 API。
- 调用快照记录的是文件内容，不是路径。若原件在规划与执行之间被替换，记录的输入就与实际运行的不再一致；快照要么把字节固定进运行目录，要么在摘要变化时中止调用。
- 回执在外部调用开始之前持久化，这样重启后仍留下可查询的标识符。

## 备选方案

**wheel 加两个运行期虚拟环境。** 这是旧设计：一个自带指纹文件的准备好的运行环境，一个不含 torch 的开发环境。否决原因是两个环境消费同一套依赖，第二个环境只换来更快的 `uv sync`，代价却是一个指纹、一个 prepare 步骤，以及一整类"我现在在哪个环境里"的故障。

**给两个 fork 单独划一棵 `upstream/` 树。** 否决：目录边界不改变我们有权限改什么，却让每条打包路径都变长。真正要紧的区分"这是不是我们的代码"，由包布局回答，而不是由父目录回答。

**单进程：把我们的路由注册到引擎的 aiohttp 上。** 自定义节点加载后技术上是现成的，还能少一个端口和一段启动顺序。首版否决，因为它把我们的可用性绑在引擎上，引擎崩溃时回执接口也一起消失。

**用 submodule 或 subtree 拉上游。** 眼下否决：两个 fork 都不追踪上游，机制会存在而没有使用者。一个钉住的 commit 加一份改动清单，已足以重建两棵树。

## 验收标准

- 全新克隆并安装锁定的 Python 与 Node 依赖后，控制器能够启动服务和引擎，并从原生页面完成一次真实 Siril 调用。
- `uv run pytest` 与 `uv run python main.py` 都在 `backend/` 下运行，且导入路径一致。
- 不做任何安装步骤时 `import astrophotoflow` 成立。
- 除单个自定义节点注册文件之外，产品代码保留在服务包、私有 UI 包与宿主集成目录中。

## 风险

- 引擎在运行期读取 `requirements.txt` 报告包版本。只用 `pyproject.toml` 取代它会让这些读取返回 `None`，而部分调用方仍会对结果调用 `.get()`，因此在所有读取方迁移之前，该文件作为兼容输入保留。
- torch 位于开发环境，所以第一次安装是几分钟与数 GB，而不是几秒。
- 引擎、业务服务和检索进程共享一个环境，依赖冲突会影响三者。
- 若不以上述边界配一条测试，引擎自带的上传路由会悄悄变成第二条数据通路。
