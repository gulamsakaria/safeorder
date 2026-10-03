import { describe, expect, it, vi } from 'vitest'
import { probeSameOrigin } from './sameOriginBackend'

const reply = (init: ResponseInit, body: string) => vi.fn(async () => new Response(body, init)) as unknown as typeof fetch

describe('probeSameOrigin', () => {
  it('accepts the SafeOrder health answer', async () => {
    expect(await probeSameOrigin(reply({ status: 200 }, '{"status":"ok"}'))).toBe(true)
  })
  it('rejects a web page, an error and a network failure', async () => {
    expect(await probeSameOrigin(reply({ status: 200 }, '<html></html>'))).toBe(false)
    expect(await probeSameOrigin(reply({ status: 404 }, '{"status":"ok"}'))).toBe(false)
    expect(await probeSameOrigin(vi.fn(async () => Promise.reject(new Error('offline'))) as unknown as typeof fetch)).toBe(false)
  })
  it('rejects other JSON', async () => {
    expect(await probeSameOrigin(reply({ status: 200 }, '{"status":"down"}'))).toBe(false)
  })
})
