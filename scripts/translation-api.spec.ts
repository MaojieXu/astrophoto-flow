/** Behaviour of the provider client: configuration, retry policy, and error surfaces. */

import { describe, expect, it, vi } from 'vitest'
import { readTranslationApiConfig, requestTranslation, type ChatMessage, type TranslationApiConfig } from './translation-api.ts'

const messages: ChatMessage[] = [
  { role: 'system', content: 'translate' },
  { role: 'user', content: 'source' },
]
const config: TranslationApiConfig = {
  baseUrl: 'https://example.test',
  apiKey: 'secret',
  model: 'model-1',
  timeoutMs: 1000,
  maxRetries: 2,
  sessionId: 'session-1',
}
const noSleep = async (): Promise<void> => {}

function ok(content: string): Response {
  return new Response(JSON.stringify({ choices: [{ message: { content } }] }), { status: 200 })
}

function failure(status: number, body = 'service trouble'): Response {
  return new Response(body, { status })
}

describe('readTranslationApiConfig', () => {
  it('applies defaults and strips a trailing slash', () => {
    const read = readTranslationApiConfig({ APF_TRANSLATION_API_KEY: 'k', APF_TRANSLATION_BASE_URL: 'https://api.example.test/v1/' })
    expect(read.apiKey).toBe('k')
    expect(read.baseUrl).toBe('https://api.example.test/v1')
    expect(read.model).toBe('deepseek-v4.1-flash')
    expect(read.timeoutMs).toBe(300_000)
    expect(read.maxRetries).toBe(3)
    expect(read.sessionId).toMatch(/^[0-9a-f-]{36}$/)
  })

  it('defaults to the Go gateway path, which bills the subscription instead of the balance', () => {
    const read = readTranslationApiConfig({ APF_TRANSLATION_API_KEY: 'k' })
    expect(read.baseUrl).toBe('https://opencode.ai/inference/go/openai/v1')
  })

  it('keeps an explicit session id', () => {
    const read = readTranslationApiConfig({ APF_TRANSLATION_API_KEY: 'k', APF_TRANSLATION_SESSION_ID: 'run-42' })
    expect(read.sessionId).toBe('run-42')
  })

  it('fails loudly without a key', () => {
    expect(() => readTranslationApiConfig({})).toThrow(/APF_TRANSLATION_API_KEY is not set/)
  })

  it('rejects a non-numeric timeout', () => {
    expect(() => readTranslationApiConfig({ APF_TRANSLATION_API_KEY: 'k', APF_TRANSLATION_TIMEOUT_MS: 'soon' })).toThrow(
      /expected a positive integer/,
    )
  })
})

describe('requestTranslation', () => {
  it('posts the conversation and returns the message content', async () => {
    const fetch = vi.fn(async () => ok('译文'))
    await expect(requestTranslation(messages, config, { fetch: fetch as unknown as typeof globalThis.fetch, sleep: noSleep })).resolves.toBe(
      '译文',
    )
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('https://example.test/chat/completions')
    expect((init.headers as Record<string, string>).authorization).toBe('Bearer secret')
    expect((init.headers as Record<string, string>)['x-opencode-session']).toBe('session-1')
    expect(JSON.parse(init.body as string)).toMatchObject({ model: 'model-1', temperature: 0, messages })
  })

  it('retries a server error and then succeeds', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(failure(503)).mockResolvedValueOnce(ok('译文'))
    const sleep = vi.fn(noSleep)
    await expect(requestTranslation(messages, config, { fetch: fetch as unknown as typeof globalThis.fetch, sleep })).resolves.toBe(
      '译文',
    )
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(sleep).toHaveBeenCalledTimes(1)
  })

  it('does not retry an authentication failure', async () => {
    const fetch = vi.fn(async () => failure(401, 'bad key'))
    const sleep = vi.fn(noSleep)
    await expect(
      requestTranslation(messages, config, { fetch: fetch as unknown as typeof globalThis.fetch, sleep }),
    ).rejects.toThrow(/401 .*bad key/)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(sleep).not.toHaveBeenCalled()
  })

  it('gives up after the retry budget', async () => {
    const fetch = vi.fn(async () => failure(429))
    await expect(
      requestTranslation(messages, config, { fetch: fetch as unknown as typeof globalThis.fetch, sleep: noSleep }),
    ).rejects.toThrow(/429/)
    expect(fetch).toHaveBeenCalledTimes(3)
  })

  it('retries a transport error and reports the attempt count', async () => {
    const fetch = vi.fn(async () => {
      throw new Error('connection reset')
    })
    await expect(
      requestTranslation(messages, config, { fetch: fetch as unknown as typeof globalThis.fetch, sleep: noSleep }),
    ).rejects.toThrow(/after 3 attempts: connection reset/)
  })

  it('rejects a response without message content', async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ choices: [] }), { status: 200 }))
    await expect(
      requestTranslation(messages, config, { fetch: fetch as unknown as typeof globalThis.fetch, sleep: noSleep }),
    ).rejects.toThrow(/no message content/)
  })
})
