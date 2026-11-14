# 双语文档

[English](README.md) | 中文

本仓库的文档会被人和 agent（智能体）阅读，因此范围内的每篇文档都以英文和简体中文维护。本页定义配对约定、门禁、范围与排除规则；[translation-rules.md](translation-rules.zh.md) 定义如何翻译；[terminology.md](terminology.md) 是术语真源。agent 的日常工作遵循 [docs/AGENTS.md](../AGENTS.md) 中的轻量路径；扩展版 [.agents/skills/astrophotoflow-translate](../../.agents/skills/astrophotoflow-translate/SKILL.md) 工作流仅在用户显式调用时可用。

## 配对约定

- **两种语言同权。** 一篇文档可以先用任一语言撰写和评审（先写中文的 Agent Note 与先写英文的一样正当），另一侧由它翻译而来。两个文件谁也不高于谁；约束它们的是二者必须说同样的话。
- **一对文档是三个同目录文件。** 英文 `foo.md`、中文 `foo.zh.md`，加一份一致性记录 `foo.i18n.yaml`，都在同一目录。不用语言目录，不用独立翻译仓库，不用中英混排的单文件。配对必须整体合并：一次变更永远不会只带一种语言而缺其余两个文件。
- **一致性记录。**`foo.i18n.yaml` 为每个仍含语言特有内容的标题分节保存一个条目。键是该分节英文标题 slug 组成的路径（第一个标题之前的文本为 `/`；重复路径依次加 `~2`、`~3`……），条目保存该分节中两侧不同的英文块与中文块各自的 hash：

  ```yaml
  /foo:
    en: 41d772192075e133
    zh: dda91c6c670cfd9d
  /foo/usage:
    en: 86940bea4a3c7ed6
    zh: de78429597783c7f
  ```

  一侧的第 `i` 个分节对应另一侧的第 `i` 个分节。每侧的 hash 覆盖该分节的全部顶层块，只排除围栏代码块——门禁已要求这类内容在两侧一致；只是碰巧相同的内容仍计入 hash。没有剩余块的分节没有条目。在两侧同时修改代码块不会改变记录；修改不同分节会改动记录中不同的行，因此 Git 默认文本合并（包括 GitHub 的合并）能组合它们。只有两个分支都修改了同一分节中计入 hash 的内容时，记录才会冲突；解决 Markdown 冲突后重新记录该配对。失去同步的配对是「按被改一侧的 diff 最小化地修补另一侧」，从不整篇重译；门禁会指出每个发生变化的分节。两侧对齐后，`pnpm verify-translation-pairing --write <pair>` 重新记录这些条目；那份 YAML diff 就是「确认一致」这个动作本身，可以被评审，也正因如此，`--write` 要求点名你确认过的配对（`--write --all` 是显式的全语料形式）。

  中文文件必须保留指向英文的反向链接；英文源必须保留指向中文的链接。记录的键取自英文标题，因此中文标题重命名不会破坏记录。
- **语言切换行。** 中文文件一律在 H1 标题后立即以 `[English](foo.md) | 中文` 链回英文；英文源在同一位置以 `English | [中文](foo.zh.md)` 互链。
- **结构与另一侧一一对应。** 标题深度与顺序、列表类型、有序列表起始编号、列表项数量、表格行列数、保留原样 query/fragment 后缀的语义链接目标，以及逐字节一致的代码块在配对两侧一一对应。相对文档链接的目标属于活跃双语语料时，英文侧使用其 `.md` 路径，中文侧使用其 `.zh.md` 路径。该范围内缺少对侧属于配对完整性错误，不得回退；范围外的目标保留原路径。完整保持规则见 [translation-rules.md](translation-rules.zh.md)。仓库既有的 Markdown 约定对 `.zh.md` 文件原样生效。

## 门禁：verify-translation-pairing

`pnpm verify-translation-pairing` 机械地强制执行这份约定：

1. 范围内的每篇文档都有完整配对。
2. 任何已存在的配对产物都完整且一致：三个文件齐全、记录为规范形式，且其条目等于根据当前内容计算出的条目（任一侧的语言特有内容改了而没重新确认配对就变红）、中文侧与英文源都带语言切换行、每条普通相对文档链接都使用源文件一侧对应的目标 locale，且结构签名按序一致：标题深度、逐字节一致的代码块（信息字符串与内容）、表格行列数、列表类型、有序列表起始编号、列表项数量，以及除切换行之外保留原样 query/fragment 后缀的语义链接目标。
3. 列为 `excluded` 的文件完全没有 `.zh.md`，也没有 `.i18n.yaml`。`.agents/notes/archived/` 下冻结的 Agent Note 不受这个持续演进的门禁约束；专用校验器会要求其现有的三个配对文件完整，并将其封存。

`pnpm verify-translation-pairing --list` 打印范围内每篇文档的当前配对状态（missing、out-of-sync 或 ok）。它从不失败；其中 `missing` 与 `out-of-sync` 行指出普通检查会拒绝的违规。

`pnpm verify-translation-pairing <pair...>` 只检查被点名的配对——配对的三个文件中的任意一个（或其裸词干）都能点名它——因此更新循环几秒内就能验证自己的配对，而不必重新扫描全语料。无参数的全语料形式才是完整文档检查所运行的内容；限定范围的绿灯永远不能替代它。

这个门禁带来的实际规则是：**当一次变更修改了已配对文档的任一侧时，同一个变更在术语指导下直接一次完成对侧文件的更新，并用 `--write <pair>` 重新记录配对。** 留下失去同步的配对的变更会变红。

门禁的限制很明确：**门禁通过意味着这组文档在当前内容上的一致性得到了确认，不代表确认本身正确可靠。** 它检查记录的 hash 与 Markdown 结构；它无法判断两侧是否在说同样的话，也无法判断措辞是否准确、术语是否得当、行文是否自然——这部分约定由评审者把关，见 [translation-rules.md](translation-rules.zh.md)。重新记录了 hash 但另一侧翻得潦草的配对能通过门禁；它不得通过评审。

## 范围与排除

**范围**：每份 `README.md`、`docs/**` 下的每篇文档，以及 `.agents/notes/**` 下的每篇活跃 Agent Note。依赖目录、被忽略的构建产物目录以及冻结的 `.agents/notes/archived/` 目录树只在发现阶段排除，不属于持续演进的翻译源文档。

**排除**（永不配对，门禁拒绝为它们建 `.zh.md` 或 `.i18n.yaml`）：

- 根 `AGENTS.md`、`docs/AGENTS.md` 与 `.agents/notes/**/AGENTS.md`：agent 指令，只以英文维护。
- [terminology.md](terminology.md)：本身即为中英对照文档。
- `.agents/notes/archived/`：冻结的历史三文件配对。[`verify-archived-agent-notes`](../../scripts/verify-archived-agent-notes.ts) 校验其完整性和内容封存记录；翻译维护绝不能重写这些文件。

**统一要求**：当前及今后纳入范围的每篇文档，合并时都必须构成完整的双语配对。[`translation-pairing.manifest.json`](../../scripts/translation-pairing.manifest.json) 只包含显式排除项；不存在逐文件推进清单、日期分界或 README 专用政策类别。

## 分工

日常更新对侧文件时，负责处理的 agent 会先加载 [terminology.md](terminology.md)，再直接一次性更新；它不会调用翻译 skill（技能）、执行单独的翻译评审轮次，也不会委派给 subagent。扩展版 [astrophotoflow-translate](../../.agents/skills/astrophotoflow-translate/SKILL.md) 技能负责分阶段流程，仅供用户显式调用。若要先得到整篇初稿，[pipeline.md](pipeline.zh.md) 描述了脚本路径；通读 diff 与记录配对仍需人工完成。门禁负责检查配对是否完整、记录的 hash、切换行、链接 locale，以及本文列出的结构签名；翻译质量、术语和签名未涵盖的结构要求仍由评审把关。
