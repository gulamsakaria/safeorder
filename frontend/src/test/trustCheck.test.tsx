import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { STRINGS } from '../i18n/strings'
import { renderApp } from './render'

async function checkSeller(user: ReturnType<typeof renderApp>['user'], query: string) {
  await user.type(screen.getByLabelText(STRINGS.bn['check.search.label']), query)
  await user.click(screen.getByRole('button', { name: STRINGS.bn['common.search'] }))
  const list = await screen.findByRole('list', { name: 'sellers' })
  await user.click(within(list).getByRole('button', { name: STRINGS.bn['check.pick'] }))
  return await screen.findByLabelText('trust-result')
}

describe('Trust Check screen', () => {
  it('shows a trusted seller with score, band and Bangla reasons', async () => {
    const { user } = renderApp('/')
    const result = await checkSeller(user, 'Shop 0001')
    expect(within(result).getByText(STRINGS.bn['band.TRUSTED'])).toBeInTheDocument()
    expect(within(result).getByTestId('score')).toHaveTextContent('৯৫')
    expect(within(result).getByText('অ্যাকাউন্টটি ৩৯৬ দিন ধরে সক্রিয়')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: STRINGS.bn['check.pay'] })).toBeEnabled()
    expect(screen.queryByText(STRINGS.bn['check.warning.title'])).not.toBeInTheDocument()
  })

  it('shows the reasons in English after switching language', async () => {
    const { user } = renderApp('/')
    const result = await checkSeller(user, 'Shop 0001')
    await user.click(screen.getByRole('button', { name: 'English' }))
    expect(within(result).getByText('Account has been active for 396 days')).toBeInTheDocument()
  })

  it('treats a limited-history seller as neutral: no score, a clear explanation', async () => {
    const { user } = renderApp('/')
    const result = await checkSeller(user, 'Shop 0003')
    expect(within(result).getAllByText(STRINGS.bn['band.LIMITED_HISTORY']).length).toBeGreaterThan(0)
    expect(within(result).queryByTestId('score')).not.toBeInTheDocument()
    expect(within(result).getByText(STRINGS.bn['check.limited.body'])).toBeInTheDocument()
  })

  it('needs an extra confirmation before paying a high-risk seller, and does not block the order', async () => {
    const { user } = renderApp('/')
    const result = await checkSeller(user, 'Shop 0002')
    expect(within(result).getByText(STRINGS.bn['band.HIGH_RISK'])).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(STRINGS.bn['check.warning.title'])

    const pay = screen.getByRole('button', { name: STRINGS.bn['check.pay'] })
    expect(pay).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: STRINGS.bn['check.warning.confirm'] }))
    expect(pay).toBeEnabled()
  })

  it('places a Safe Order and lands on the tracker with the sandbox code', async () => {
    const { user } = renderApp('/')
    await checkSeller(user, 'Shop 0001')
    await user.click(screen.getByRole('button', { name: STRINGS.bn['check.pay'] }))

    const submit = screen.getByRole('button', { name: STRINGS.bn['check.order.submit'] })
    expect(submit).toBeDisabled()
    await user.type(screen.getByLabelText(/টাকার পরিমাণ/), '2800')
    await user.click(submit)

    expect(await screen.findByTestId('order-status')).toHaveTextContent(STRINGS.bn['status.HELD'])
    expect(screen.getByTestId('sandbox-code')).toHaveTextContent(/^[০-৯]{6}$/)
  })

  it('says so when no seller matches', async () => {
    const { user } = renderApp('/')
    await user.type(screen.getByLabelText(STRINGS.bn['check.search.label']), 'zzz-nobody')
    await user.click(screen.getByRole('button', { name: STRINGS.bn['common.search'] }))
    expect(await screen.findByText(STRINGS.bn['check.search.none'])).toBeInTheDocument()
  })

  it('searches by wallet number', async () => {
    const { user } = renderApp('/')
    const result = await checkSeller(user, 'SIM-W-S0004')
    expect(within(result).getByText(STRINGS.bn['band.CAUTION'])).toBeInTheDocument()
  })

  it('does not search for an empty query', async () => {
    renderApp('/')
    expect(screen.getByRole('button', { name: STRINGS.bn['common.search'] })).toBeDisabled()
    await waitFor(() => expect(screen.queryByRole('list', { name: 'sellers' })).not.toBeInTheDocument())
  })
})
