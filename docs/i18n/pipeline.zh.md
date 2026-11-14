# 脚本驱动的翻译

[English](pipeline.md) | 中文

本页讲机器路径：[`translate.ts`](../../scripts/translate.ts) 组装已评审的提示词、调用 OpenAI 兼容服务、写出对侧文件，并记录这次运行。人工路径见 [README.md](README.zh.md) 与 [translation-rules.md](translation-rules.zh.md)。两条路径产出相同的三文件配对，因此门禁无法分辨某一页出自哪条路径，任何一条也不得跳过一致性记录。

## 命令

```sh
cp .env.example .env
pnpm translate docs/i18n/pipeline.md
pnpm translate docs/i18n/pipeline.md --dry-run
pnpm verify-translation-prompt
pnpm verify-translation-pairing --write docs/i18n/pipeline.zh.md
```

第一条命令把凭据模板复制一次。第二条写出对侧文件；`--dry-run` 只打印组装好的请求形态，不调用服务。后两条用于检查提示词资产，并在通读 diff 之后记录配对。

`pnpm translate` 依据源文件名推导对侧路径（`.md` 推 `.zh.md`，反向亦然），其他后缀一律拒绝。`.agents/notes/archived/` 下的源文件是封存件，不属于翻译工作。

## 机器路径不负责判断什么

服务返回三段内容，调用方只保留 `<final>` 并修正语言切换行，因为模型无从得知全新配对的目标文件名。命令从不记录配对：机器写出的译文在有人读过之前都只是草稿，因此 `--write` 必须留在通读 diff 之后的显式一步。[README.md](README.zh.md) 说明了门禁全绿能证明什么；省掉这次通读，是任何门禁都看不见的失败。

## 凭据

`APF_TRANSLATION_API_KEY` 来自环境变量或仓库外的根 `.env`；`.env.example` 列出变量名。默认路由是 OpenCode 的 Go 网关 `https://opencode.ai/inference/go/openai/v1`，走订阅而不是余额，承载模型 `deepseek-v4.1-flash`；`APF_TRANSLATION_BASE_URL` 与 `APF_TRANSLATION_MODEL` 改为别处，超时与重试变量限定尝试次数。一次运行在 `x-opencode-session` 里只发一个会话 id。缺少密钥时命令直接失败而不是跳过，因此一次运行不会静默通过。

每次调用都会在 `.artifacts/translations/` 下写入记录，包含模型、提示词路径与两侧内容哈希。记录留在仓库之外，所以日志泄漏不会带出凭据或过期文档。
