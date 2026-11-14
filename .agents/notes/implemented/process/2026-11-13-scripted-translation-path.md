# Agent Note: A scripted translation path beside the manual pass

Status: implemented

English | [中文](2026-11-13-scripted-translation-path.zh.md)

## Problem

Every bilingual pair is authored by hand: one pass writes both sides, and the pairing gate then proves structure, switchers, links, and the recorded hashes. That pass reads well, but each new page costs a reviewer-grade effort, and the prompt asset at [translation-prompt.md](../../../docs/i18n/translation-prompt.md) with its reviewed fixtures had no consumer. A checked-in prompt with no caller is decorative: nothing failed when it drifted, and a reader could not tell whether the contract was live.

## Decision

[translate.ts](../../../scripts/translate.ts) renders that prompt with the terminology table and the three reviewed fixture pairs, calls an OpenAI-compatible chat completion, keeps the `<final>` section, corrects the language switcher, and writes the counterpart. It never records the pair, because a machine draft is unread prose and `--write` still means "a person confirmed these exact contents".

Credentials come from `APF_TRANSLATION_*` variables or a root `.env` that stays git-ignored; a missing key fails the command instead of skipping it, every call writes a record under `.artifacts/translations/` with the model, the prompt path, and both content hashes, and [verify-translation-prompt](../../../scripts/verify-translation-prompt.ts) joins the gates so the prompt asset and the fixture list are checked like any other contract.

## Gateway routing

The first real call reached a gateway that bills per token and answered `402 Payment Required` against an empty balance while a subscription was active, because the path decides the billing source: the plain inference path spends prepaid balance, the Go path spends the subscription. The default base URL is the Go path, a call through it reports `billing_source: go`, and every request carries `x-opencode-session` so the gateway can route and cache. Model identifiers differ per route, so the model stays a variable rather than a constant.

## Alternatives considered

**Leave translation entirely manual.** Rejected: the gate is good at structure and blind to prose, so every new page keeps a long hand pass that no check verifies anyway.

**Call the model from a skill instead of a script.** Rejected: a skill runs in an agent session with no fixed prompt, no retry policy, and no record, so two runs over the same document could differ with nothing written down.

**Record the pair from the translate command.** Rejected: `--write` currently means a person confirmed the contents. Recording from a command would make that sentence false while the gate still passed.

## Consequences

The prompt asset and its fixtures have a consumer, so drifting them now fails a gate. Translating a new page becomes draft, read, fix, then record. The repository holds no credential and no run log, and the sealed archive stays out of scope because it is not evolving translation source.
