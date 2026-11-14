/** Verify that the committed translation prompt renders and parses as documented. */

import {
  loadReviewedExamples,
  loadTerminology,
  readRepositoryFile,
  repositoryRoot,
  REVIEWED_EXAMPLE_PATHS,
  TRANSLATION_PROMPT_PATH,
} from './translation-corpus.ts'
import {
  consumeTranslationResponse,
  documentedTranslationPromptPlaceholders,
  parseTranslationResponse,
  renderTranslationPrompt,
  renderTranslationRequest,
  renderTranslationResponse,
  TRANSLATION_PROMPT_PLACEHOLDERS,
} from './translation-prompt.ts'

const root = repositoryRoot()
const read = (path: string): string => readRepositoryFile(root, path)

try {
  const mode = process.argv[2]
  if (mode !== undefined && mode !== '--snapshot') throw new Error(`unsupported argument ${JSON.stringify(mode)}`)
  const document = read(TRANSLATION_PROMPT_PATH)
  const terminology = loadTerminology(root)
  // Synthetic reviewed examples, not live documents: editing a paired document must not
  // churn the prompt snapshot. Each pair mirrors the other side's structure and uses
  // terminology-table forms. The prompt documents the same list, so both sides are checked.
  const examples = loadReviewedExamples(root)
  for (const [english] of REVIEWED_EXAMPLE_PATHS) {
    const listed = `\`scripts/fixtures/translation-prompt/${english}\``
    if (!document.includes(listed)) throw new Error(`prompt does not list the reviewed example pair ${listed}`)
  }
  const sourceDocument = read('scripts/fixtures/translation-prompt/snapshot-note.md')
  const recordedResponse = read('scripts/fixtures/translation-prompt/response.txt')
  const documented = documentedTranslationPromptPlaceholders(document)
  if (documented.join('\n') !== TRANSLATION_PROMPT_PLACEHOLDERS.join('\n')) {
    throw new Error(`placeholder table must list exactly: ${TRANSLATION_PROMPT_PLACEHOLDERS.join(', ')}`)
  }

  const englishInput = { sourceLanguage: 'English' as const, sourceFilename: 'snapshot-note.md', terminology }
  const englishSource = renderTranslationPrompt(document, englishInput)
  const chineseSource = renderTranslationPrompt(document, {
    sourceLanguage: 'Chinese',
    sourceFilename: 'snapshot-note.zh.md',
    terminology,
  })
  if (englishSource.includes('{{') || chineseSource.includes('{{')) throw new Error('rendered prompt contains an unresolved placeholder')
  if (!englishSource.includes('from English to Chinese')) throw new Error('English-source render does not translate into Chinese')
  if (!chineseSource.includes('from Chinese to English')) throw new Error('Chinese-source render does not translate into English')

  const example = /```xml\n([\s\S]*?)\n```/.exec(englishSource)?.[1]
  if (example === undefined) throw new Error('rendered prompt has no three-section response example')
  parseTranslationResponse(example)

  const roundTrip = { translation: 'first pass\n\nwith **markdown**', review: '- 无修正', final: 'final text' }
  const parsed = parseTranslationResponse(renderTranslationResponse(roundTrip))
  if (JSON.stringify(parsed) !== JSON.stringify(roundTrip)) throw new Error('three-section response does not round-trip')

  const request = renderTranslationRequest(document, { ...englishInput, sourceDocument, examples })
  if (request.targetFilename !== 'snapshot-note.zh.md') throw new Error('English request resolves the wrong target filename')
  const expectedRoles = ['system', ...examples.flatMap(() => ['user', 'assistant']), 'user']
  if (request.messages.map(message => message.role).join('\n') !== expectedRoles.join('\n')) {
    throw new Error('reviewed examples are not assembled as system, example pairs, then source')
  }
  const consumed = consumeTranslationResponse(recordedResponse, englishInput)
  const expectedFinalPrefix = [
    '# 快照说明',
    '',
    '[English](snapshot-note.md) | 中文',
    '',
  ].join('\n')
  if (!consumed.final.startsWith(expectedFinalPrefix)) {
    throw new Error('recorded response does not receive the canonical target switcher under the translated heading')
  }

  if (mode === '--snapshot') {
    process.stdout.write(`${JSON.stringify({ request, response: consumed }, null, 2)}\n`)
  } else {
    console.log('verify-translation-prompt: both directions render, reviewed examples assemble, and the consumed response is target-path correct.')
  }
} catch (error) {
  const message = error instanceof Error ? error.message : String(error)
  console.error(`verify-translation-prompt: ${message}`)
  process.exit(1)
}
