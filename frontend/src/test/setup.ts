import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { resetStore } from '../mocks/data'
import { server } from '../mocks/server'

// The tests run against the same mock handlers the browser mock uses.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  resetStore()
  sessionStorage.clear()
  localStorage.clear()
})
afterAll(() => server.close())
