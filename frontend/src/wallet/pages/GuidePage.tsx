import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAction } from '../../api/hooks'
import { Button, Card } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { useAuth } from '../AuthProvider'
import { wallet } from '../calls'
import { PageTitle, Problem } from '../ui'

const DEMO_PIN = '12345'
const SCENARIOS = ['honest', 'silent', 'unclaimed', 'falseclaim', 'fakeproof'] as const

function randomPhone(prefix: string): string {
  const digits = Array.from({ length: 8 }, () => Math.floor(Math.random() * 10)).join('')
  return `${prefix}${digits}`
}

/** The role-play guide: how to play buyer and seller in one browser, and the five stories to try. */
export function GuidePage() {
  const { t, num } = useI18n()
  const { me, signUp, switchTo, accounts } = useAuth()
  const navigate = useNavigate()
  const [made, setMade] = useState<{ buyer: string; seller: string } | null>(null)

  const create = useAction(async () => {
    // two fresh accounts: the second one is a seller. The tab ends up signed in as the buyer.
    const sellerPhone = randomPhone('0182')
    const buyerPhone = randomPhone('0171')
    await signUp('Demo Seller', sellerPhone, DEMO_PIN)
    await wallet.sellerMode({ shop_name: 'Demo Shop', category: 'clothing' })
    await signUp('Demo Buyer', buyerPhone, DEMO_PIN)
    setMade({ buyer: buyerPhone, seller: sellerPhone })
  })
  const swap = useAction(async (phone: string) => {
    const account = accounts.find((a) => a.phone === phone)
    if (account) await switchTo(account)
    navigate('/home')
  })

  return (
    <>
      <PageTitle back={me ? '/more' : '/welcome'}>{t('w.guide.title')}</PageTitle>
      <Card>
        <p className="text-sm">{t('w.guide.intro')}</p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
          <li>{t('w.guide.tip.tabs')}</li>
          <li>{t('w.guide.tip.switch')}</li>
          <li>{t('w.guide.tip.admin')}</li>
        </ul>
      </Card>

      <Card>
        <h3 className="mb-1 font-bold">{t('w.guide.quick.title')}</h3>
        <p className="mb-3 text-sm text-slate-600">{t('w.guide.quick.sub')}</p>
        <Button className="w-full" disabled={create.pending} onClick={() => void create.run()}>
          {create.pending ? t('w.working') : t('w.guide.quick.go')}
        </Button>
        {create.error && <div className="mt-2"><Problem error={create.error} /></div>}
        {made && (
          <div className="mt-3 space-y-2 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-950">
            <p className="font-bold">{t('w.guide.quick.done')}</p>
            <p>
              {t('w.guide.quick.buyer')}: <b>{num(made.buyer)}</b> · {t('w.guide.quick.pin')}: <b>{num(DEMO_PIN)}</b>
            </p>
            <p>
              {t('w.guide.quick.seller')}: <b>{num(made.seller)}</b> · {t('w.guide.quick.pin')}: <b>{num(DEMO_PIN)}</b>
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" onClick={() => void swap.run(made.buyer)}>
                {t('w.guide.quick.asbuyer')}
              </Button>
              <Button variant="secondary" onClick={() => void swap.run(made.seller)}>
                {t('w.guide.quick.asseller')}
              </Button>
            </div>
          </div>
        )}
      </Card>

      <h3 className="px-1 font-bold text-white">{t('w.guide.stories')}</h3>
      {SCENARIOS.map((s, index) => (
        <Card key={s}>
          <h4 className="mb-1 font-bold">
            {num(index + 1)}. {t(`w.guide.s.${s}.title`)}
          </h4>
          <p className="text-sm text-slate-700">{t(`w.guide.s.${s}.steps`)}</p>
        </Card>
      ))}
    </>
  )
}
