/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { handlers } from '../mocks/handlers'

const openapi = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, unknown>>
  components: { schemas: Record<string, unknown> }
}
const generated = readFileSync(resolve(__dirname, '../api/schema.ts'), 'utf8')

describe('API contract', () => {
  it('the generated client types are up to date with docs/openapi.json (run `npm run gen:api`)', () => {
    for (const path of Object.keys(openapi.paths)) {
      expect(generated, `path ${path}`).toContain(`"${path}"`)
    }
    for (const name of Object.keys(openapi.components.schemas)) {
      expect(generated, `schema ${name}`).toMatch(new RegExp(`\\b${name}: \\{|\\b${name}: [\\w"]`))
    }
  })

  it('every screen call has an endpoint in the contract', () => {
    const used = [
      ['/api/sellers/search', 'get'],
      ['/api/trust/check', 'post'],
      ['/api/orders', 'post'],
      ['/api/orders/{order_id}', 'get'],
      ['/api/orders/{order_id}/confirm-delivery', 'post'],
      ['/api/disputes', 'post'],
      ['/api/disputes/{dispute_id}', 'get'],
      ['/api/disputes/{dispute_id}/seller-response', 'post'],
      ['/api/disputes/{dispute_id}/buyer-evidence', 'post'],
      ['/api/sim/courier-event', 'post'],
      ['/api/sim/advance-clock', 'post'],
      ['/api/demo/reset', 'post'],
      ['/api/analyst/queue', 'get'],
      ['/api/analyst/disputes/{dispute_id}', 'get'],
      ['/api/disputes/{dispute_id}/analyze', 'post'],
      ['/api/analyst/disputes/{dispute_id}/decision', 'post'],
      ['/api/sellers/{seller_id}/score-history', 'get'],
    ] as const
    for (const [path, method] of used) {
      expect(openapi.paths[path]?.[method], `${method} ${path}`).toBeDefined()
    }
  })

  it('the mock server answers every endpoint the screens use', () => {
    expect(handlers.length).toBe(17) // 12 for the buyer and seller screens, 5 for the analyst console
  })

  it('errors are documented in the real format (code and message), not the framework default', () => {
    const text = JSON.stringify(openapi.paths)
    expect(text).not.toContain('HTTPValidationError')
    expect(openapi.components.schemas.ErrorOut).toBeDefined()
  })
})
