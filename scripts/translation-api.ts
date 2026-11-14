/**
 * OpenAI-compatible chat completion client for the translation pipeline.
 *
 * Configuration lives in the environment and only the variable names are
 * checked in, so a credential never reaches the repository. The client retries
 * only failures a retry can fix (429, 5xx, network errors, timeouts); an
 * authentication or request error fails immediately, because retrying it wastes
 * time and hides a configuration mistake.
 *
 * The default route is the OpenCode inference gateway, which serves the same
 * Chat Completions shape as a provider's own API. It reads a stable
 * `x-opencode-session` header to route requests and reuse prompt caching, so
 * one run of the pipeline reports one session id.
 */

import { randomUUID } from 'node:crypto'

export interface TranslationApiConfig {
  /** Service root, without a trailing `/chat/completions`. */
  baseUrl: string
  apiKey: string
  model: string
  /** Per-attempt timeout in milliseconds. */
  timeoutMs: number
  /** Retries after the first attempt. */
  maxRetries: number
  /** Stable conversation id; the gateway keys routing and prompt caching off it. */
  sessionId: string
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export const DEFAULT_BASE_URL = 'https://opencode.ai/inference/go/openai/v1'
export const DEFAULT_MODEL = 'deepseek-v4.1-flash'
export const DEFAULT_TIMEOUT_MS = 300_000
export const DEFAULT_MAX_RETRIES = 3

const RETRYABLE_STATUS = new Set([408, 409, 429, 500, 502, 503, 504])

function positiveInteger(value: string | undefined, fallback: number): number {
  if (value === undefined || value.trim() === '') return fallback
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`translation: expected a positive integer, got ${JSON.stringify(value)}`)
  return parsed
}

/** Read configuration from the environment, failing loudly on a missing key. */
export function readTranslationApiConfig(env: Record<string, string | undefined> = process.env): TranslationApiConfig {
  const apiKey = env.APF_TRANSLATION_API_KEY?.trim()
  if (apiKey === undefined || apiKey === '') {
    throw new Error('translation: APF_TRANSLATION_API_KEY is not set; see .env.example')
  }
  const baseUrl = env.APF_TRANSLATION_BASE_URL?.trim() || DEFAULT_BASE_URL
  return {
    baseUrl: baseUrl.replace(/\/+$/, ''),
    apiKey,
    model: env.APF_TRANSLATION_MODEL?.trim() || DEFAULT_MODEL,
    timeoutMs: positiveInteger(env.APF_TRANSLATION_TIMEOUT_MS, DEFAULT_TIMEOUT_MS),
    maxRetries: positiveInteger(env.APF_TRANSLATION_MAX_RETRIES, DEFAULT_MAX_RETRIES),
    sessionId: env.APF_TRANSLATION_SESSION_ID?.trim() || randomUUID(),
  }
}

/** Dependencies a test replaces. */
export interface TranslationApiDeps {
  fetch: typeof fetch
  sleep: (ms: number) => Promise<void>
}

const defaultDeps: TranslationApiDeps = {
  fetch: (input, init) => fetch(input, init),
  sleep: ms => new Promise(resolve => setTimeout(resolve, ms)),
}

function backoffMs(attempt: number): number {
  const base = 1000 * 2 ** (attempt - 1)
  return base + Math.floor(Math.random() * 250)
}

function contentOf(payload: unknown): string {
  const choices = (payload as { choices?: { message?: { content?: unknown } }[] }).choices
  const content = choices?.[0]?.message?.content
  if (typeof content !== 'string' || content.trim() === '') {
    throw new Error('translation: response carried no message content')
  }
  return content
}

/**
 * Send one conversation and return the assistant message.
 *
 * @param messages - System prompt, reviewed example turns, then the source document.
 * @param config - Endpoint, model, and retry policy.
 * @param deps - Injected transport for tests.
 */
export async function requestTranslation(
  messages: ChatMessage[],
  config: TranslationApiConfig,
  deps: TranslationApiDeps = defaultDeps,
): Promise<string> {
  const endpoint = `${config.baseUrl}/chat/completions`
  const body = JSON.stringify({ model: config.model, messages, temperature: 0, stream: false })

  for (let attempt = 0; ; attempt++) {
    const attemptNumber = attempt + 1
    let response: Response
    try {
      response = await deps.fetch(endpoint, {
        method: 'POST',
        headers: {
          authorization: `Bearer ${config.apiKey}`,
          'content-type': 'application/json',
          'x-opencode-session': config.sessionId,
        },
        body,
        signal: AbortSignal.timeout(config.timeoutMs),
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      if (attemptNumber > config.maxRetries) throw new Error(`translation: request failed after ${attemptNumber} attempts: ${message}`)
      await deps.sleep(backoffMs(attemptNumber))
      continue
    }

    if (response.ok) return contentOf(await response.json())

    const detail = (await response.text()).trim().slice(0, 400)
    if (!RETRYABLE_STATUS.has(response.status) || attemptNumber > config.maxRetries) {
      throw new Error(`translation: ${response.status} ${response.statusText}${detail === '' ? '' : ` — ${detail}`}`)
    }
    await deps.sleep(backoffMs(attemptNumber))
  }
}
