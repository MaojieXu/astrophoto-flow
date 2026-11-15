# Terminology

本表约定本仓库的中英术语统一译法。只收录实际出现、且译法可能分歧的术语；未收录的术语按 [translation-rules.md](translation-rules.md) 的中英互译待定术语流程处理，定下后补入本表。

**通用规则：**
- “中文”列为中文译文的正文默认用词。若该列为英文，则中文译文的正文中保留英文不翻译。
- 首次出现按“首次出现”列书写（带括号注释）；后续出现只写括号前的部分（可能为中文，也可能为英文），不出现括号内的注释。
- “不要译作”列为严格禁止的译法。
- 如果某术语已经作为另一个术语的组成部分被括注过（如 `agent（智能体）` 中已包含 `agent` 的括注），则该术语后续单独出现时无需再次括注。

## 缩写类（中英文文本中均使用缩写）

| English | 中文 | 首次出现 | 不要译作 | 备注 |
|---|---|---|---|---|
| API | API | | | |
| CI | CI | | | |
| CLI | CLI | CLI（命令行界面） | | |
| FITS | FITS | | | 天文图像格式，正文与代码均保持大写 |
| JSON | JSON | | | |
| MCP | MCP | | | |
| PR | PR | PR（Pull Request） | | |
| UI | UI | UI（用户界面） | | |
| XISF | XISF | | | 天文图像格式，正文与代码均保持大写 |

## 英文类（中英文文本中均使用英文）

| English | 中文 | 首次出现 | 不要译作 | 备注 |
|---|---|---|---|---|
| Agent Note | Agent Note | | 智能体注记、智能体笔记 | 仓库定义的决策记录类型，涵盖提案、已实现决策和被否决提案；中文对侧 H1 保持固定前缀 `# Agent Note: `，标题中不加术语括注 |
| agent | agent | agent（智能体） | | agent 组合词（agent skill、coding agent 等）整体保留英文；未括注过 agent 时首现按对应组合词或 agent 行处理 |
| coding agent | coding agent | | 编程智能体 | agent 组合词，正文保留英文 |
| fixture | fixture | fixture（测试前置数据） | | |
| manifest | manifest | manifest（清单） | | |
| mock | mock | | | 保留英文；指测试替身 |
| schema | schema | | | |
| skill | skill | skill（技能） | | |
| slug | slug | | 短横式标题 | 标题生成的锚点路径片段 |

## 双语类（中英文文本各自使用中英文）

| English | 中文 | 首次出现 | 不要译作 | 备注 |
|---|---|---|---|---|
| artifact | 产物 | | 制品 | |
| asset | 素材 | | 资产、资源 | 纳入库中管理与追溯的图像文件；代码标识 `asset` 保持原样 |
| calibration | 校准 | | 标定 | |
| canvas | 画布 | | | 原生画布，节点编排的载体 |
| content token | 内容标记 | | 内容令牌 | 画布内容标记，代码标识 `content_token` 保持原样 |
| counterpart | 对侧文件 | | 对应物、配对物 | 双语配对语境；泛指“另一侧”时可写「另一侧」 |
| dataset | 数据集 | | | 数据集成员顺序属于受保护状态 |
| equipment | 设备 | | 器材 | 设备快照为受保护状态 |
| fingerprint | 指纹 | | | |
| graph | 图 | | 图表 | 画布上的处理图；与 `workflow` 区分 |
| import | 导入 | | | |
| node | 节点 | | 结点 | |
| operation | 操作 | | 算子 | 画布编辑以 `operation_id` 标识 |
| original | 原件 | | 原始文件 | 采集产生的原始文件，受原件保护约束 |
| pairing | 配对 | | | |
| preview | 预览 | | 缩略图 | 预览不作为科学输入；`thumbnail` 才译为「缩略图」 |
| receipt | 收据 | | 回执单 | 执行回执，代码标识 `receipt` 保持原样 |
| result | 结果 | | | 显式保存的结果产物 |
| run | 运行 | | 执行过程 | 一次执行；后端记录为 `task`（任务） |
| sidecar record | 伴随记录 | | 旁挂记录 | 与文档同目录的伴随记录文件 |
| snapshot | 快照 | | 瞬照 | |
| soft-delete | 移入回收站 | | 软删除 | 删除先入回收站，可恢复 |
| source of truth | 真源 | | 事实来源、唯一来源 | |
| task | 任务 | | 作业 | 一次运行的后端记录 |
| trash | 回收站 | | 垃圾箱 | |
| workbench | 工作台 | | 工作空间 | 与 `workspace`（工作区）区分 |
| workflow | 工作流 | | 流程 | 需要与图区分时写「处理图」 |
| workspace | 工作区 | | 工作台 | 配置与运行状态按工作区隔离 |
