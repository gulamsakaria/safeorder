import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAction } from '../../api/hooks'
import { Button, Card } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { useAuth } from '../AuthProvider'
import { wallet } from '../calls'
import { Icons } from '../icons'
import { PageTitle, PinField, Problem } from '../ui'

function Item({
  icon,
  tone,
  label,
  to,
  onClick,
}: {
  icon: ReactNode
  tone: string
  label: string
  to?: string
  onClick?: () => void
}) {
  const body = (
    <span className="flex min-h-14 w-full items-center gap-3 px-1 text-left">
      <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${tone}`}>{icon}</span>
      <span className="flex-1 font-bold text-slate-900">{label}</span>
      <span aria-hidden="true" className="text-slate-400">
        ›
      </span>
    </span>
  )
  return to ? (
    <Link to={to}>{body}</Link>
  ) : (
    <button type="button" className="w-full" onClick={onClick}>
      {body}
    </button>
  )
}

export function MorePage() {
  const { t, toggle } = useI18n()
  const { me, accounts, switchTo, signOut } = useAuth()
  const navigate = useNavigate()
  const [pinOpen, setPinOpen] = useState(false)
  const [oldPin, setOldPin] = useState('')
  const [newPin, setNewPin] = useState('')
  const [changed, setChanged] = useState(false)
  const changePin = useAction(async () => {
    await wallet.changePin({ old_pin: oldPin, new_pin: newPin })
    setChanged(true)
    setOldPin('')
    setNewPin('')
  })
  const swap = useAction(async (index: number) => {
    await switchTo(accounts[index])
    navigate('/home')
  })
  if (!me) return null
  const others = accounts.map((a, index) => ({ a, index })).filter(({ a }) => a.phone !== me.phone)

  return (
    <>
      <PageTitle>{t('w.nav.more')}</PageTitle>

      <Card>
        <p className="mb-1 text-xs font-bold uppercase text-slate-500">{t('w.more.settings')}</p>
        <div className="divide-y divide-slate-100">
          <Item icon={Icons.lock} tone="bg-amber-100 text-amber-700" label={t('w.more.pin')} onClick={() => setPinOpen((v) => !v)} />
          <Item icon={Icons.globe} tone="bg-emerald-100 text-emerald-700" label={t('w.more.language')} onClick={toggle} />
          <Item icon={Icons.shop} tone="bg-rose-100 text-rose-700" label={me.is_seller ? t('w.tile.seller') : t('w.seller.become')} to="/seller" />
        </div>
        {pinOpen && (
          <div className="mt-3 space-y-3 rounded-xl bg-slate-50 p-3">
            <PinField id="old-pin" label={t('w.more.pin.old')} value={oldPin} onChange={setOldPin} />
            <PinField id="new-pin" label={t('w.more.pin.new')} value={newPin} onChange={setNewPin} />
            {changePin.error && <Problem error={changePin.error} />}
            {changed && <p className="text-sm font-semibold text-emerald-800">{t('w.more.pin.done')}</p>}
            <Button disabled={oldPin.length !== 5 || newPin.length !== 5 || changePin.pending} onClick={() => void changePin.run()}>
              {t('w.more.pin.save')}
            </Button>
          </div>
        )}
      </Card>

      <Card>
        <p className="mb-1 text-xs font-bold uppercase text-slate-500">{t('w.more.accounts')}</p>
        <div className="divide-y divide-slate-100">
          {others.map(({ a, index }) => (
            <Item
              key={a.phone}
              icon={Icons.switch}
              tone="bg-indigo-100 text-indigo-700"
              label={t('w.more.switchto', { name: a.name })}
              onClick={() => void swap.run(index)}
            />
          ))}
          <Item icon={Icons.user} tone="bg-sky-100 text-sky-700" label={t('w.more.addaccount')} to="/guide" />
        </div>
        {swap.error && <div className="mt-2"><Problem error={swap.error} /></div>}
      </Card>

      <Card>
        <p className="mb-1 text-xs font-bold uppercase text-slate-500">{t('w.more.help')}</p>
        <div className="divide-y divide-slate-100">
          <Item icon={Icons.guide} tone="bg-teal-100 text-teal-700" label={t('w.tile.guide')} to="/guide" />
          <Item icon={Icons.shield} tone="bg-violet-100 text-violet-700" label={t('w.tile.check')} to="/check" />
          <Item icon={Icons.chart} tone="bg-slate-200 text-slate-700" label={t('nav.metrics')} to="/metrics" />
          {me.role === 'ADMIN' && (
            <Item icon={Icons.admin} tone="bg-red-100 text-red-700" label={t('w.more.admin')} to="/admin" />
          )}
        </div>
      </Card>

      <Card>
        <Item
          icon={Icons.logout}
          tone="bg-red-100 text-red-700"
          label={t('w.more.logout')}
          onClick={() => void signOut().then(() => navigate('/welcome'))}
        />
      </Card>
    </>
  )
}
