/**
 * Translate one document with the reviewed prompt and record the run.
 *
 * The command writes the target file only when the model response parses, then
 * prints the two steps that make the result acceptable: record the pair and run
 * the gates. It never records the pair itself, because a machine-written
 * translation still needs a human reading before the pairing record claims it
 * was confirmed.
 */

import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { basename, dirname, join, resolve } from 'node:path'
import { readTranslationApiConfig, requestTranslation, type TranslationApiConfig } from './translation-api.ts'
import {
  loadReviewedExamples,
  loadTerminology,
  readRepositoryFile,
  repositoryRoot,
  TRANSLATION_PROMPT_PATH,
} from './translation-corpus.ts'
import { consumeTranslationResponse, renderTranslationRequest } from './translation-prompt.ts'

export type TranslationLanguage = 'English' | 'Chinese'

export interface TranslateOptions {
  /** Source documents, relative to the repository root or absolute. */
  inputs: string[]
  /** Print the assembled request instead of calling the service. */
  dryRun: boolean
  /** Override `APF_TRANSLATION_MODEL`. */
  model?: string
}

export interface TranslationTarget {
  target: string
  sourceLanguage: TranslationLanguage
}

export interface TranslationRunLog {
  model: string
  baseUrl: string
  prompt: string
  source: string
  target: string
  sourceLanguage: TranslationLanguage
  sourceSha256: string
  finalSha256: string
  recordedAt: string
}

/** Derive the counterpart path and the source language from one side. */
export function deriveTranslationTarget(source: string): TranslationTarget {
  if (source.endsWith('.zh.md')) {
    return { target: `${source.slice(0, -'.zh.md'.length)}.md`, sourceLanguage: 'Chinese' }
  }
  if (source.endsWith('.md')) return { target: `${source.slice(0, -'.md'.length)}.zh.md`, sourceLanguage: 'English' }
  throw new Error(`translate: expected a Markdown source, got ${JSON.stringify(source)}`)
}

/** Parse `translate <source...> [--dry-run] [--model <id>]`. */
export function parseTranslateArgs(argv: string[]): TranslateOptions {
  const inputs: string[] = []
  let dryRun = false
  let model: string | undefined
  for (let index = 0; index < argv.length; index++) {
    const argument = argv[index] as string
    if (argument === '--dry-run') {
      dryRun = true
      continue
    }
    if (argument === '--model') {
      const value = argv[index + 1]
      if (value === undefined || value.startsWith('--')) throw new Error('translate: --model needs a model id')
      model = value
      index++
      continue
    }
    if (argument.startsWith('--')) throw new Error(`translate: unsupported option ${JSON.stringify(argument)}`)
    inputs.push(argument)
  }
  if (inputs.length === 0) throw new Error('translate: name at least one Markdown source')
  return { inputs, dryRun, model }
}

/** Read a root `.env` when present, so the documented copy step is enough. */
function loadDotEnv(root: string): void {
  const path = join(root, '.env')
  if (existsSync(path)) process.loadEnvFile(path)
}
/** Path of the run record, one file per translation attempt. */
export function translationLogPath(root: string, target: string, recordedAt: string): string {
  const slug = target.replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'translation'
  return join(root, '.artifacts/translations', `${recordedAt.replace(/[:.]/g, '-')}-${slug}.json`)
}

function sha256(text: string): string {
  return createHash('sha256').update(text, 'utf8').digest('hex')
}

async function main(): Promise<void> {
  const options = parseTranslateArgs(process.argv.slice(2))
  const root = repositoryRoot()
  loadDotEnv(root)
  const document = readRepositoryFile(root, TRANSLATION_PROMPT_PATH)
  const terminology = loadTerminology(root)
  const examples = loadReviewedExamples(root)
  const config: TranslationApiConfig | undefined = options.dryRun ? undefined : { ...readTranslationApiConfig() }
  if (config !== undefined && options.model !== undefined) config.model = options.model

  for (const input of options.inputs) {
    const source = resolve(root, input)
    const sourceDocument = readRepositoryFile(root, input)
    const { target, sourceLanguage } = deriveTranslationTarget(input)
    const request = renderTranslationRequest(document, {
      sourceLanguage,
      sourceFilename: basename(source),
      terminology,
      examples,
      sourceDocument,
    })
    if (config === undefined) {
      console.log(`dry run: ${input} → ${target} (${request.messages.length} messages, ${sourceDocument.length} characters)`)
      continue
    }

    const response = await requestTranslation(request.messages, config)
    const consumed = consumeTranslationResponse(response, { sourceLanguage, sourceFilename: basename(source) })
    const targetPath = join(root, target)
    mkdirSync(dirname(targetPath), { recursive: true })
    writeFileSync(targetPath, consumed.final, 'utf8')

    const recordedAt = new Date().toISOString()
    const log: TranslationRunLog = {
      model: config.model,
      baseUrl: config.baseUrl,
      prompt: TRANSLATION_PROMPT_PATH,
      source: input,
      target,
      sourceLanguage,
      sourceSha256: sha256(sourceDocument),
      finalSha256: sha256(consumed.final),
      recordedAt,
    }
    const logPath = translationLogPath(root, target, recordedAt)
    mkdirSync(dirname(logPath), { recursive: true })
    writeFileSync(logPath, `${JSON.stringify(log, null, 2)}\n`, 'utf8')

    console.log(`translated ${input} → ${target} with ${config.model}`)
    console.log(`next: read the diff, then run \`pnpm verify-translation-pairing --write ${target}\` and \`pnpm check\``)
  }
}

if (process.argv[1] !== undefined && import.meta.filename === resolve(process.argv[1])) {
  main().catch((error: unknown) => {
    // The client and this command both prefix their messages; print the prefix once.
    const message = error instanceof Error ? error.message : String(error)
    console.error(`translate: ${message.replace(/^translation: /, '')}`)
    process.exit(1)
  })
}
