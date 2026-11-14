/** Argument, path, and run-record behaviour of the translate command. */

import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { deriveTranslationTarget, parseTranslateArgs, translationLogPath } from './translate.ts'

describe('deriveTranslationTarget', () => {
  it('maps an English source to its Chinese counterpart', () => {
    expect(deriveTranslationTarget('README.md')).toEqual({ target: 'README.zh.md', sourceLanguage: 'English' })
    expect(deriveTranslationTarget('docs/i18n/README.md')).toEqual({
      target: 'docs/i18n/README.zh.md',
      sourceLanguage: 'English',
    })
  })

  it('maps a Chinese source back to its English counterpart', () => {
    expect(deriveTranslationTarget('.agents/notes/README.zh.md')).toEqual({
      target: '.agents/notes/README.md',
      sourceLanguage: 'Chinese',
    })
  })

  it('rejects a non-Markdown source', () => {
    expect(() => deriveTranslationTarget('docs/notes.txt')).toThrow(/expected a Markdown source/)
  })
})

describe('parseTranslateArgs', () => {
  it('collects inputs and flags in any order', () => {
    expect(parseTranslateArgs(['README.md', '--dry-run', '--model', 'other-model'])).toEqual({
      inputs: ['README.md'],
      dryRun: true,
      model: 'other-model',
    })
  })

  it('requires at least one source', () => {
    expect(() => parseTranslateArgs([])).toThrow(/name at least one Markdown source/)
  })

  it('rejects an unknown option', () => {
    expect(() => parseTranslateArgs(['--write'])).toThrow(/unsupported option "--write"/)
  })

  it('rejects a model flag without a value', () => {
    expect(() => parseTranslateArgs(['README.md', '--model', '--dry-run'])).toThrow(/--model needs a model id/)
  })
})

describe('translationLogPath', () => {
  it('keeps one readable record per attempt under .artifacts', () => {
    const path = translationLogPath('/repo', 'docs/i18n/README.zh.md', '2026-11-13T21:20:00.000Z')
    expect(path).toBe(join('/repo', '.artifacts/translations/2026-11-13T21-20-00-000Z-docs-i18n-README-zh-md.json'))
  })
})
