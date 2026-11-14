# Agent Note: 一个仓库，一个运行环境

Status: proposed

[English](2026-11-13-repository-and-runtime-shape.md) | 中文

## 问题

旧布局把产品切成三份：`src/astrophotoflow` 里的 Python 服务、`engine/` 下完整的 ComfyUI 副本、`frontend/` 下完整的 ComfyUI_frontend 副本，再用构建脚本和第二个运行期虚拟环境把它们接起来。切分的每一份代价都是维护：一个装着引擎归档的 wheel、一个 console script、一个持有运行期指纹的 bootstrap 工具、一份生成的 CLI，以及两个必须同步的环境。对"一个人在一台机器上运行"的产品，结构应该让人一眼回答两个问题：哪些代码是我的，哪个环境把它装起来。

## 提案

`src/` 下三个目录，各一个环境：

```text
src/workbench/backend/     # uv environment
    main.py, comfy/, nodes.py …     ComfyUI source
    astrophotoflow/                 our service package, importable without installing
    custom_nodes/astrophotoflow/    one registration file that points at the package
    web/                            frontend build output, git-ignored
    pyproject.toml, uv.lock, tests/
src/workbench/frontend/    # pnpm environment
    upstream source plus src/platform/astrophotoflow/
src/mcp/                   # pnpm environment, Node, only talks HTTP
```

我们的包放在引擎树里，且从不安装：引擎从 `backend/` 起跑，`import astrophotoflow` 按目录位置解析，服务以 `python -m astrophotoflow` 启动。没有 wheel，没有 console script，没有运行期指纹。

目录名保留 `workbench`；产品名仍是 AstroPhotoFlow，这样改目录名永远不会改动产品叫什么。

引擎与我们的 HTTP 服务仍是同一环境里的两个进程。引擎拥有图、队列、进度与取消；我们的服务拥有素材、数据集、回执，以及画布编辑的归属规则。两者分开，意味着引擎崩溃后工作区 API 仍能回答回执相关的问题。

分发按[决定](../simplification/2026-11-14-no-distribution-engineering.zh.md)不做；前端 fork 处于[冻结](../simplification/2026-11-14-freeze-the-frontend-fork.zh.md)状态；工具面是[一个客户端](2026-11-14-node-mcp-for-the-tool-surface.zh.md)。

## 数据归属

`backend/astrophotoflow/interfaces/http` 是唯一写入已登记素材、数据集、图或回执的入口。引擎的两处行为必须显式处理，而不是假设它不存在：

- ComfyUI 自带上传与素材路由。它们拥有临时输入与输出；它们不能变成第二条登记路径，原生保存动作也必须经过我们的归属与修订规则。
- 调用快照记录的是文件内容，不是路径。若原件在规划与执行之间被替换，记录的输入就与实际运行的不再一致；快照要么把字节固定进运行目录，要么在摘要变化时中止调用。
- 回执在外部调用开始之前持久化，这样重启后仍留下可查询的标识符。

## 备选方案

**wheel 加两个运行期虚拟环境。** 这是旧设计：一个自带指纹文件的准备好的运行环境，一个不含 torch 的开发环境。否决原因是两个环境消费同一套依赖，第二个环境只换来更快的 `uv sync`，代价却是一个指纹、一个 prepare 步骤，以及一整类"我现在在哪个环境里"的故障。

**给两个 fork 单独划一棵 `upstream/` 树。** 否决：目录边界不改变我们有权限改什么，却让每条打包路径都变长。真正要紧的区分"这是不是我们的代码"，由包布局回答，而不是由父目录回答。

**单进程：把我们的路由注册到引擎的 aiohttp 上。** 自定义节点加载后技术上是现成的，还能少一个端口和一段启动顺序。首版否决，因为它把我们的可用性绑在引擎上，引擎崩溃时回执接口也一起消失。

**用 submodule 或 subtree 拉上游。** 眼下否决：两个 fork 都不追踪上游，机制会存在而没有使用者。一个钉住的 commit 加一份改动清单，已足以重建两棵树。

## 验收标准

- 全新克隆、一次 `uv sync`、一次前端构建、`python main.py`，能打开页面并完成一次真实 Siril 调用。
- `uv run pytest` 与 `uv run python main.py` 都在 `backend/` 下运行，且导入路径一致。
- 不做任何安装步骤时 `import astrophotoflow` 成立。
- 除 `custom_nodes/astrophotoflow/` 之外，没有目录把我们的文件与上游文件混在一起。

## 风险

- 引擎在运行期读取 `requirements.txt` 报告包版本。只用 `pyproject.toml` 取代它会让这些读取返回 `None`，而部分调用方仍会对结果调用 `.get()`，因此在所有读取方迁移之前，该文件作为兼容输入保留。
- torch 位于开发环境，所以第一次安装是几分钟与数 GB，而不是几秒。
- 两个进程共用一个环境，依赖冲突仍然是两者共同的一次性故障点。
- 若不以上述边界配一条测试，引擎自带的上传路由会悄悄变成第二条数据通路。
