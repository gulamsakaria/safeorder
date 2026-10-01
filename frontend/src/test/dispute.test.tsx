import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { STRINGS } from '../i18n/strings'
import { placeOrder, post, renderApp } from './render'

const T = STRINGS.bn

async function deliveredOrder() {
  const order = await placeOrder()
  await post('/api/sim/courier-event', { order_id: order.id, status: 'delivered' })
  return order
}

describe('buyer dispute form', () => {
  it('files a dispute and lands on the dispute page', async () => {
    const order = await deliveredOrder()
    const { user } = renderApp(`/order/${order.id}/report`)
    const submit = await screen.findByRole('button', { name: T['report.submit'] })
    expect(submit).toBeDisabled() // a claim is required

    await user.selectOptions(screen.getByLabelText(T['report.type']), 'WRONG_ITEM')
    await user.type(screen.getByLabelText(T['report.claim']), 'ভুল জুতা এসেছে')
    await user.type(screen.getByLabelText(T['report.evidence']), 'বাক্সের লেবেলে অন্য মডেল লেখা')
    await user.click(submit)

    expect(await screen.findByTestId('dispute-status')).toHaveTextContent(T['dispute.status.OPEN'])
    expect(screen.getByText('ভুল জুতা এসেছে')).toBeInTheDocument()
    expect(screen.getByText(T['report.type.WRONG_ITEM'])).toBeInTheDocument()
    expect(screen.getByText('বাক্সের লেবেলে অন্য মডেল লেখা')).toBeInTheDocument()
    expect(screen.getByText(T['dispute.waiting'])).toBeInTheDocument()
  })

  it('disables the photo upload and says why (photos are text-only in this version)', async () => {
    const order = await deliveredOrder()
    renderApp(`/order/${order.id}/report`)
    expect(await screen.findByRole('button', { name: T['report.photo'] })).toBeDisabled()
    expect(screen.getByText(T['report.photo.note'])).toBeInTheDocument()
  })

  it('refuses the form when a problem can no longer be reported', async () => {
    const order = await deliveredOrder()
    await post('/api/sim/advance-clock', { hours: 73 })
    renderApp(`/order/${order.id}/report`)
    expect(await screen.findByText(T['report.notallowed'])).toBeInTheDocument()
  })

  it('links the order page to the dispute once it exists', async () => {
    const order = await deliveredOrder()
    await post('/api/disputes', { order_id: order.id, claim_text: 'x' })
    renderApp(`/order/${order.id}`)
    expect(await screen.findByText(T['order.report.disputed'])).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: T['order.report'] })).not.toBeInTheDocument()
  })

  it('lets the buyer add more evidence', async () => {
    const order = await deliveredOrder()
    const dispute = await (await post('/api/disputes', { order_id: order.id, claim_text: 'broken' })).json()
    const { user } = renderApp(`/dispute/${dispute.id}`)
    await user.type(await screen.findByLabelText(T['dispute.addEvidence']), 'স্ক্র্যাচের ছবি আছে')
    await user.click(screen.getByRole('button', { name: T['dispute.addEvidence.send'] }))
    expect(await screen.findByText('স্ক্র্যাচের ছবি আছে')).toBeInTheDocument()
  })
})

describe('seller response form', () => {
  async function dispute() {
    const order = await deliveredOrder()
    return (await (await post('/api/disputes', { order_id: order.id, claim_text: 'broken' })).json()) as {
      id: string
    }
  }

  it('shows the claim and the deadline, and takes a response', async () => {
    const d = await dispute()
    const { user } = renderApp(`/dispute/${d.id}?as=seller`)
    const form = await screen.findByLabelText('seller-form')
    expect(within(form).getByText(T['seller.deadline'], { exact: false })).toBeInTheDocument()
    expect(within(form).getByTestId('countdown')).toHaveTextContent(/^(১ দিন ২৩ ঘণ্টা|২ দিন ০ ঘণ্টা)$/)

    const submit = within(form).getByRole('button', { name: T['seller.submit'] })
    expect(submit).toBeDisabled()
    await user.type(within(form).getByLabelText(T['seller.response']), 'ঠিকভাবে প্যাক করেছিলাম')
    await user.type(within(form).getByLabelText(T['seller.evidence']), 'কুরিয়ার ট্র্যাকিং নম্বর আছে')
    await user.click(submit)

    await waitFor(() =>
      expect(screen.getByTestId('dispute-status')).toHaveTextContent(T['dispute.status.SELLER_RESPONDED']),
    )
    expect(screen.getAllByText('ঠিকভাবে প্যাক করেছিলাম').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/আপনার জবাব জমা হয়েছে/)).toBeInTheDocument()
  })

  it('closes the form when the deadline has passed', async () => {
    const d = await dispute()
    await post('/api/sim/advance-clock', { hours: 49 })
    renderApp(`/dispute/${d.id}?as=seller`)
    const form = await screen.findByLabelText('seller-form')
    expect(await within(form).findByRole('alert')).toHaveTextContent(T['seller.deadline.passed'])
    expect(within(form).queryByRole('button', { name: T['seller.submit'] })).not.toBeInTheDocument()
  })

  it('switches between the buyer and the seller view', async () => {
    const d = await dispute()
    const { user } = renderApp(`/dispute/${d.id}`)
    await screen.findByTestId('dispute-status')
    expect(screen.queryByLabelText('seller-form')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: T['dispute.view.seller'] }))
    expect(await screen.findByLabelText('seller-form')).toBeInTheDocument()
  })
})

describe('user-written text is shown as text, never as markup', () => {
  it('escapes HTML in claims and evidence', async () => {
    const order = await deliveredOrder()
    const payload = '<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script><b>bold</b>'
    const res = await post('/api/disputes', {
      order_id: order.id,
      claim_text: payload,
      evidence_text: payload,
    })
    const d = (await res.json()) as { id: string }
    const { container } = renderApp(`/dispute/${d.id}`)
    await screen.findByTestId('dispute-status')

    expect(screen.getAllByText(payload).length).toBeGreaterThanOrEqual(2) // literal text on screen
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined()
  })
})

describe('demo controls', () => {
  it('moves the clock and triggers a courier event', async () => {
    const order = await placeOrder()
    const { user } = renderApp('/demo')
    await user.type(screen.getByLabelText(T['demo.order']), order.id)
    await user.click(screen.getByRole('button', { name: T['courier.delivered'] }))
    expect(await screen.findByTestId('demo-note')).toHaveTextContent(T['status.DELIVERED'])

    await user.click(screen.getByRole('button', { name: /\+72/ }))
    await waitFor(() => expect(screen.getByTestId('demo-note')).toHaveTextContent('HOLD_EXPIRED'))
  })
})
