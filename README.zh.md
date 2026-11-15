# AstroPhotoFlow

[English](README.md) | 中文

AstroPhotoFlow 是一个通过浏览器操作的本地天文成像工作台：它保存图像素材与数据集，把真实天文软件注册为画布节点，并让你在原生画布上组装、运行、查看和保存结果。用户在 Web 应用中操作，脚本驱动 CLI（命令行界面），外部 agent（智能体）使用平台 MCP 服务器；该服务器负责编排与查询，但从不执行图。

本仓库包含仅保留图像能力的 ComfyUI 引擎与前端 fork、依赖配置、MCP 生命周期工具和 Windows 交付脚本。业务服务与检索集成由活跃提案规定。发行验证要求真实入口存在，才能接受可安装的工作台。

## 本仓库包含的内容

- [架构](docs/architecture.zh.md)：依赖归属、原生画布归属与通信边界。
- [开发](docs/development.zh.md)：运行时、依赖安装与环境隔离。
- [Windows 交付](docs/release.zh.md)：agent 安装、MCP 启动与评审后发布。
- [Agent Notes](.agents/notes/README.zh.md)：提案、已实现决策与冻结的历史。
- [文档规则](docs/AGENTS.md)：文档位置与双语维护。

## 依赖

在仓库根目录使用 Node 26 和 pnpm 11.28.5：

```sh
pnpm install --frozen-lockfile --ignore-scripts
```

[开发参考](docs/development.zh.md)介绍独立的前端 workspace 与 uv 管理的 Python 环境。验证范围以当前任务要求为准。
