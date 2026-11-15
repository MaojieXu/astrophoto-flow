# 开发环境

[English](development.md) | 中文

本参考介绍从仓库根目录安装依赖。MCP 包构建 stdio 生命周期入口；业务 API 与检索服务仍需按[架构](architecture.zh.md)完成各自集成。agent 安装与公开产物遵循 [Windows 交付](release.zh.md)。

## 运行时与锁文件

使用 Python 3.12、Node `>=26.8.2 <27`、pnpm 11.28.5 与 uv。根目录 `.node-version` 选择 Node 26.13.1；后端 `.python-version` 选择 Python 3.12。依赖版本在配置中声明，再解析进锁文件。

根 pnpm workspace 拥有仓库工具与 `src/mcp`。前端拥有独立的 pnpm workspace 和锁文件，其中包含私有 UI（用户界面）包。后端拥有一个 uv 项目与锁文件，包含图像引擎、业务库和检索库。CPU PyTorch 来自其依赖配置中的显式 CPU 索引。

## 安装依赖

在仓库根目录运行以下命令，所需工具必须位于 `PATH`：

```sh
uv sync --project src/workbench/backend --locked
pnpm install --frozen-lockfile --ignore-scripts
pnpm --dir src/workbench/frontend install --frozen-lockfile --ignore-scripts
```

成功安装会以零退出码结束，并创建项目环境。pnpm 命令禁止生命周期脚本，因此不会安装 hook 或修改 Git 配置。它们只安装依赖；需要单独准备的原生工具仍须在使用前完成准备。

uv 默认管理 `src/workbench/backend/.venv`。隔离验证时，先把 `UV_PROJECT_ENVIRONMENT` 设为一个可丢弃目录的绝对路径，再运行同一个同步命令。替代环境验证完成前保留已有环境。不要依赖继承的系统包来证明锁文件完整。

LangGraph 是库依赖。安装它不会构建参考语料、选择 embedding 或 reranker 模型，也不会下载其权重。[知识库提案](../.agents/notes/proposed/feature/2026-11-14-agent-knowledge-base-rag.zh.md)维护该流程。

## 配置与验证

根目录 `.env.example` 描述的是翻译工具凭据，不是工作台设置或模型凭据。[工作区提案](../.agents/notes/proposed/feature/2026-11-14-workbench-settings-and-lifecycle.zh.md)定义独立的工作台配置。令牌、数据库、缓存、模型文件与生成产物不进入版本控制。

环境验证检查锁定依赖解析，以及隔离环境中的导入。锁文件兼容 Windows 不能证明 Windows 原生启动成功；把平台专属命令写成可用说明之前，先在 Windows shell 中验证。

遵循当前任务要求的验证范围。环境或文档更新未要求时，不新建测试目录，也不运行全仓静态检查、构建或测试。文档修改仍须更新对侧文件，并按[配对契约](i18n/README.zh.md)重新记录确切配对。
