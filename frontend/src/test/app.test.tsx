import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { STRINGS } from '../i18n/strings'
import { renderApp } from './render'

const BANNER_BN = 'স্যান্ডবক্স - কৃত্রিম ডেটা, কোনো আসল টাকা নয়'

describe('layout', () => {
  it.each(['/', '/order/O-0001', '/order/O-0001/report', '/dispute/D-0001', '/demo', '/nowhere'])(
    'always shows the sandbox banner (%s)',
    async (route) => {
      renderApp(route)
      expect(await screen.findByTestId('sandbox-banner')).toHaveTextContent(BANNER_BN)
    },
  )

  it('is Bangla by default and switches to English and back', async () => {
    const { user } = renderApp('/')
    expect(document.documentElement.lang).toBe('bn')
    expect(screen.getByText(STRINGS.bn['check.title'])).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'English' }))
    expect(screen.getByText(STRINGS.en['check.title'])).toBeInTheDocument()
    expect(screen.getByTestId('sandbox-banner')).toHaveTextContent(STRINGS.en['banner.text'])
    expect(document.documentElement.lang).toBe('en')
    expect(localStorage.getItem('safeorder.lang')).toBe('en')

    await user.click(screen.getByRole('button', { name: 'বাংলা' }))
    expect(screen.getByText(STRINGS.bn['check.title'])).toBeInTheDocument()
  })

  it('remembers the chosen language', async () => {
    localStorage.setItem('safeorder.lang', 'en')
    // no explicit initial language: the provider reads the stored choice
    const { render } = await import('@testing-library/react')
    const { MemoryRouter } = await import('react-router-dom')
    const { I18nProvider } = await import('../i18n/I18nProvider')
    const { default: App } = await import('../App')
    render(
      <MemoryRouter>
        <I18nProvider>
          <App />
        </I18nProvider>
      </MemoryRouter>,
    )
    expect(screen.getByText(STRINGS.en['check.title'])).toBeInTheDocument()
  })

  it('has a Bangla and an English text for every key', () => {
    expect(Object.keys(STRINGS.bn).sort()).toEqual(Object.keys(STRINGS.en).sort())
    for (const [key, text] of Object.entries(STRINGS.bn)) {
      expect(text.trim(), key).not.toBe('')
    }
  })

  it('the Bangla UI uses Bengali script', () => {
    const latinOnly = Object.entries(STRINGS.bn).filter(
      ([key, text]) =>
        !/[ঀ-৿]/.test(text) && !['lang.toggle', 'check.search.placeholder', 'check.model'].includes(key),
    )
    // a few strings legitimately stay Latin (names, placeholders, codes); none of the sentences do
    expect(latinOnly.map(([k]) => k)).toEqual(['demo.hours'].filter(() => false))
  })
})
