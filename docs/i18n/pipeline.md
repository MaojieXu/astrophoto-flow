# Script-driven translation

English | [中文](pipeline.zh.md)

This page covers the machine path: [`translate.ts`](../../scripts/translate.ts) assembles the reviewed prompt, calls an OpenAI-compatible service, writes the counterpart, and records the run. The human path stays in [README.md](README.md) and [translation-rules.md](translation-rules.md). Both paths produce the same three-file pair, so the gate cannot tell which one produced a page, and neither route may skip the record.

## Commands

```sh
cp .env.example .env
pnpm translate docs/i18n/pipeline.md
pnpm translate docs/i18n/pipeline.md --dry-run
pnpm verify-translation-prompt
pnpm verify-translation-pairing --write docs/i18n/pipeline.zh.md
```

The first line copies the credential template once. The second writes the counterpart; `--dry-run` prints the assembled request shape instead of calling the service. The last two check the prompt asset and record the pair after the diff has been read.

`pnpm translate` derives the counterpart from the source name (`.md` to `.zh.md`, and the reverse) and refuses every other suffix. A source under `.agents/notes/archived/` is a sealed artifact, so it is not translation work.

## What the machine path does not decide

The service returns three sections, and the caller keeps `<final>` and corrects the language switcher, because the model cannot know the target filename of a brand-new pair. The command never records the pair: a machine-written translation is a draft until a person reads it, so `--write` stays a deliberate step after the diff review. [README.md](README.md) states what a green gate proves; skipping that reading is the one failure no gate can see.

## Credentials

`APF_TRANSLATION_API_KEY` comes from the environment or a root `.env` outside the repository; `.env.example` lists the variable names. The default route is OpenCode's Go gateway, `https://opencode.ai/inference/go/openai/v1`, which bills the subscription rather than the balance and serves `deepseek-v4.1-flash`; `APF_TRANSLATION_BASE_URL` and `APF_TRANSLATION_MODEL` point the client elsewhere, and the timeout and retry variables bound attempts. One run sends one session id in `x-opencode-session`. A missing key fails the command instead of skipping it, so a run cannot pass silently.

Every call writes a record under `.artifacts/translations/` holding the model, the prompt path, and both content hashes. The records stay outside the repository, so a leak of the log cannot ship a credential or a stale document.
