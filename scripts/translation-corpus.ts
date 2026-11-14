/**
 * Prompt inputs shared by the prompt verifier and the translate command.
 *
 * Both consumers must assemble exactly the same corpus, so the reviewed example
 * pairs are listed once here and the paths are kept in step with the "Reviewed
 * example pairs" list in `docs/i18n/translation-prompt.md`.
 */

import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import type { TranslationExample } from './translation-prompt.ts'

export const TRANSLATION_PROMPT_PATH = 'docs/i18n/translation-prompt.md'
export const TERMINOLOGY_PATH = 'docs/i18n/terminology.md'

const FIXTURE_ROOT = 'scripts/fixtures/translation-prompt'

/** Reviewed example pairs, English side first. */
export const REVIEWED_EXAMPLE_PATHS = [
  ['examples/workbench.md', 'examples/workbench.zh.md'],
  ['examples/rules.md', 'examples/rules.zh.md'],
  ['examples/note.md', 'examples/note.zh.md'],
] as const

/** Repository root, resolved from this file's location. */
export function repositoryRoot(fromDirectory: string = import.meta.dirname): string {
  return resolve(fromDirectory, '..')
}

/** Read one repository file as UTF-8 text. */
export function readRepositoryFile(root: string, path: string): string {
  return readFileSync(join(root, path), 'utf8')
}

/** The terminology table, injected whole into the prompt. */
export function loadTerminology(root: string): string {
  return readRepositoryFile(root, TERMINOLOGY_PATH)
}

/** The reviewed example pairs, read as whole documents. */
export function loadReviewedExamples(root: string): TranslationExample[] {
  return REVIEWED_EXAMPLE_PATHS.map(([english, chinese]) => ({
    english: readRepositoryFile(root, `${FIXTURE_ROOT}/${english}`),
    chinese: readRepositoryFile(root, `${FIXTURE_ROOT}/${chinese}`),
  }))
}
