# AstroPhotoFlow

[English](README.md) | 中文

AstroPhotoFlow 是一个通过浏览器操作的本地天文成像工作台：它保存图像素材与数据集，把真实天文软件注册为画布节点，并让你在原生画布上组装、运行、查看和保存结果。用户在 Web 应用中操作，脚本驱动 CLI（命令行界面），外部 agent（智能体）使用平台 MCP 服务器；该服务器负责编排与查询，但从不执行图。

本仓库承载的正是这些规则所在的层。产品源码树尚未就位：这次重写从代码必须满足的流程开始。

## 本仓库包含的内容

- `AGENTS.md`：在本仓库中工作的 agent 所需遵循的常设指令。
- `.agents/notes/`：决策语料库、其生命周期规则以及冻结的归档。
- `.agents/skills/`：用于保持笔记、文档与翻译一致的规程。
- `docs/AGENTS.md`：文档标准；`docs/i18n/`：双语配对契约。
- `scripts/`：用于检查上述所有内容的门禁。

## 检查

先安装一次依赖，然后运行门禁：

```sh
pnpm install
pnpm check
pnpm check:full
```

`pnpm check` 运行文档、笔记与配对门禁；`pnpm check:full` 还会加入类型检查和单元测试。每个失败都会点名它所依据的规则。
