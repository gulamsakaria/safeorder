import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { I18nProvider } from '../i18n/I18nProvider'
import type { Lang } from '../i18n/strings'

/** Renders the whole app at a route, in Bangla unless told otherwise. */
export function renderApp(route = '/', lang: Lang = 'bn') {
  const user = userEvent.setup()
  const view = render(
    <MemoryRouter initialEntries={[route]}>
      <I18nProvider initial={lang}>
        <App />
      </I18nProvider>
    </MemoryRouter>,
  )
  return { user, ...view }
}

const API = 'http://localhost:8000'

/** Direct calls to the mock API, to set up state the way the demo panel would. */
export async function post(path: string, body: unknown): Promise<Response> {
  return fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function placeOrder(sellerId = 'S-0001', amount = 2800) {
  const res = await post('/api/orders', {
    buyer_id: 'B-000001',
    seller_id: sellerId,
    amount_bdt: amount,
    product_category: 'shoes',
  })
  return (await res.json()) as { id: string; delivery_code: string }
}
