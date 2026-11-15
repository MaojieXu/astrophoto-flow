# 架构

[English](architecture.md) | 中文

后端依赖配置把图像引擎、业务 API 和检索库放在同一个 uv 项目中。前端与 MCP 分别使用独立的 pnpm workspace。MCP 提供 Windows 生命周期工具；业务服务与检索集成由[运行布局提案](../.agents/notes/proposed/architecture/2026-11-13-repository-and-runtime-shape.zh.md)定义。

## 依赖归属

| 归属 | 声明的技术栈 | 职责 |
|---|---|---|
| `src/workbench/backend/` | Python 3.12、uv、CPU PyTorch、aiohttp | 图像节点与原生图执行 |
| 后端业务依赖 | FastAPI、Pydantic 2、Uvicorn、SQLAlchemy 2、Alembic、SQLite | 业务 HTTP API、校验、持久化与迁移 |
| 后端检索依赖 | LangGraph、NumPy | 本地检索流程；语料与索引独立于图像素材 |
| `src/workbench/frontend/` | Vue 3、TypeScript、Vite、Tailwind CSS 4、PrimeVue | 原生工作台与宿主组件系统 |
| 私有 UI（用户界面）包 | TanStack Vue Query、Zod 4、OpenAPI 生成器 | 服务数据、校验与生成客户端 |
| `src/mcp/` | Node 26、FastMCP TS、Zod 4 | stdio 任务工具与 HTTP 客户端 |

[开发参考](development.zh.md)维护安装命令和环境位置。依赖配置与锁文件维护精确版本。

## 原生画布与业务 API

ComfyUI 拥有可编辑图、工作流文件、草稿、保存、撤销、子图、执行队列、进度与取消。Pinia 保存原生与本地界面状态；Vue Query 保存服务数据与缓存。私有 UI 包接收宿主控件并发出事件，不导入原生单例。

FastAPI 边界拥有素材、数据集、设备、校准、业务任务与操作收据。SQLAlchemy 访问它的 SQLite 数据库，Alembic 管理 schema 迁移。科学文件独立于数据库存放。引擎不持有第二本素材账本。

画布命令遵循[原生画布提案](../.agents/notes/proposed/architecture/2026-11-14-native-canvas-and-service-receipts.zh.md)：业务 API 校验并准备操作，HTTPX 调用带认证的 aiohttp 桥接，桥接通过 WebSocket 向选定浏览器页面发送命令。页面调用原生图操作并返回收据。整图执行仍走原生 prompt 与队列路径。

## MCP 与知识库

[MCP 提案](../.agents/notes/proposed/architecture/2026-11-14-node-mcp-for-the-tool-surface.zh.md)让 FastMCP TS 负责工具注册和协议处理。业务工具调用 HTTP API。服务 OpenAPI 文档是生成 TypeScript 客户端与 Zod 校验器的来源；MCP 不导入 UI 包。

固定生命周期引导是唯一允许创建进程的例外。它调用已安装控制器，再核对服务身份与 HTML 端点，才返回本机地址。[Windows 交付参考](release.zh.md)维护安装、控制器契约与两阶段发布流程。

[知识库提案](../.agents/notes/proposed/feature/2026-11-14-agent-knowledge-base-rag.zh.md)把检索代码放在工作台后端。控制器使用后端环境启动独立的 Python 检索进程。MCP 暴露搜索与读取工具；检索返回带引用的段落，由外部 agent（智能体）使用。语料、索引与模型缓存拥有独立的数据目录。

## 边界

业务服务是自身领域数据库的唯一写入者。原生图文件由 ComfyUI 持有；收据中的输入或图快照是证据，不是另一份可编辑图。结果未知时，先按已有操作 id 查询，再决定是否显式重试。

[模块边界规则](../scripts/verify-module-boundaries.ts)约束源码导入。[Agent Notes](../.agents/notes/README.zh.md)维护决策理由与尚未构建的行为；本参考不会把提案变成可运行接口。
