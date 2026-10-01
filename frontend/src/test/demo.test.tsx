import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp } from './render'

describe('demo page scenarios', () => {
  it('loads the scenarios and links each one to the right screen', async () => {
    const { user } = renderApp('/demo')
    await user.click(await screen.findByRole('button', { name: 'সিনারিও লোড করুন' }))

    const happy = await screen.findByTestId('scenario-happy_path')
    expect(within(happy).getByRole('link', { name: /অর্ডার O-0001/ })).toHaveAttribute('href', '/order/O-0001')
    expect(within(happy).getByText(/ডেলিভারি কোড/)).toBeInTheDocument()
    expect(within(await screen.findByTestId('scenario-fake_seller')).getByRole('link')).toHaveAttribute(
      'href',
      expect.stringContaining('/?q=Synthetic%20Shop'),
    )
    expect(screen.getByTestId('demo-note')).toHaveTextContent('সিনারিও লোড হয়েছে')
  })

  it('a scenario link runs the Trust Check for the linked seller', async () => {
    renderApp('/?q=Synthetic%20Shop%200002')
    const result = await screen.findByLabelText('trust-result')
    await waitFor(() => expect(within(result).getByTestId('score')).toHaveTextContent('৯'))
  })
})
