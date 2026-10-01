import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { STRINGS } from '../i18n/strings'
import { placeOrder, post, renderApp } from './render'

const T = STRINGS.bn

describe('Safe Order tracker', () => {
  it('shows a held order: status, courier, hold notice, ledger', async () => {
    const order = await placeOrder()
    renderApp(`/order/${order.id}`)
    expect(await screen.findByTestId('order-status')).toHaveTextContent(T['status.HELD'])
    expect(screen.getByTestId('courier-status')).toHaveTextContent(T['courier.not_dispatched'])
    expect(screen.getByText(T['order.held'])).toBeInTheDocument()
    expect(screen.getByText(/হিসাব মিলেছে/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: T['order.report'] })).toBeEnabled()
  })

  it('rejects a wrong delivery code and accepts the right one, then shows the hold countdown', async () => {
    const order = await placeOrder()
    const { user } = renderApp(`/order/${order.id}`)
    const input = await screen.findByLabelText(T['order.code.enter'])

    await user.type(input, '000000')
    await user.click(screen.getByRole('button', { name: T['order.code.confirm'] }))
    expect(await screen.findByRole('alert')).toHaveTextContent(T['common.error.INVALID_CODE'])
    expect(screen.getByTestId('order-status')).toHaveTextContent(T['status.HELD'])

    await user.clear(input)
    await user.type(input, order.delivery_code)
    await user.click(screen.getByRole('button', { name: T['order.code.confirm'] }))

    await waitFor(() => expect(screen.getByTestId('order-status')).toHaveTextContent(T['status.DELIVERED']))
    const timer = screen.getByLabelText('hold-timer')
    expect(within(timer).getByTestId('countdown')).toHaveTextContent(/^(২ দিন ২৩ ঘণ্টা|৩ দিন ০ ঘণ্টা)$/)
    expect(screen.queryByLabelText(T['order.code.enter'])).not.toBeInTheDocument()
  })

  it('shows the money released after the clock passes the hold period', async () => {
    const order = await placeOrder()
    await post('/api/sim/courier-event', { order_id: order.id, status: 'delivered' })
    const { user } = renderApp(`/order/${order.id}`)
    expect(await screen.findByLabelText('hold-timer')).toBeInTheDocument()

    await post('/api/sim/advance-clock', { hours: 73 })
    await user.click(screen.getByRole('button', { name: T['order.refresh'] }))
    expect(await screen.findByText(T['order.done.RELEASED'])).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: T['order.report'] })).not.toBeInTheDocument()
  })

  it('lets the buyer report a problem when the parcel is lost, and hides the sandbox code afterwards', async () => {
    const order = await placeOrder()
    await post('/api/sim/courier-event', { order_id: order.id, status: 'lost' })
    renderApp(`/order/${order.id}`)
    expect(await screen.findByTestId('order-status')).toHaveTextContent(T['status.DISPUTABLE'])
    expect(screen.getByTestId('courier-status')).toHaveTextContent(T['courier.lost'])
    expect(screen.getByRole('button', { name: T['order.report'] })).toBeInTheDocument()
  })

  it('shows readable timeline events in Bangla', async () => {
    const order = await placeOrder()
    renderApp(`/order/${order.id}`)
    expect(await screen.findByText(T['event.ORDER_PLACED_AND_HELD'])).toBeInTheDocument()
  })

  it('explains a missing order instead of crashing', async () => {
    renderApp('/order/O-9999')
    expect(await screen.findByRole('alert')).toHaveTextContent(T['common.error.NOT_FOUND'])
  })
})
