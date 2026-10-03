import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAction } from '../../api/hooks'
import { useSameOriginBackend } from '../../api/sameOriginBackend'
import { Button, Card, Label, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { useAuth } from '../AuthProvider'
import { PinField, Problem, Segmented } from '../ui'

type Mode = 'login' | 'register'

export function WelcomePage() {
  const { t } = useI18n()
  const { me, signIn, signUp, accounts, switchTo } = useAuth()
  const navigate = useNavigate()
  const backend = useSameOriginBackend()
  const [mode, setMode] = useState<Mode>('login')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [pin, setPin] = useState('')

  const submit = useAction(async () => {
    if (mode === 'login') await signIn(phone, pin)
    else await signUp(name, phone, pin)
    navigate('/home', { replace: true })
  })
  const quick = useAction(async (index: number) => {
    await switchTo(accounts[index])
    navigate('/home', { replace: true })
  })

  if (me) return <Navigate to="/home" replace />
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void submit.run()
  }

  if (backend === 'no') {
    return (
      <Card tone="warn">
        <p className="font-semibold">{t('w.nobackend')}</p>
      </Card>
    )
  }

  return (
    <>
      <Card>
        <h2 className="mb-1 text-lg font-bold">{t('w.welcome.title')}</h2>
        <p className="mb-3 text-sm text-slate-600">{t('w.welcome.sub')}</p>
        <Segmented
          value={mode}
          onChange={(m) => {
            setMode(m)
            submit.clearError()
          }}
          options={[
            { value: 'login', label: t('w.login') },
            { value: 'register', label: t('w.register') },
          ]}
        />
        <form onSubmit={onSubmit} className="mt-4 space-y-3">
          {mode === 'register' && (
            <div>
              <Label htmlFor="w-name">{t('w.name')}</Label>
              <TextInput id="w-name" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} />
            </div>
          )}
          <div>
            <Label htmlFor="w-phone">{t('w.phone')}</Label>
            <TextInput
              id="w-phone"
              type="tel"
              inputMode="numeric"
              placeholder="017XXXXXXXX"
              value={phone}
              maxLength={14}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <PinField id="w-pin" label={t('w.pin')} value={pin} onChange={setPin} />
          <p className="rounded-xl bg-amber-50 p-3 text-xs font-semibold text-amber-900">{t('w.pin.warning')}</p>
          {submit.error && <Problem error={submit.error} />}
          <Button
            type="submit"
            className="w-full"
            disabled={submit.pending || !phone || pin.length !== 5 || (mode === 'register' && name.trim().length < 2)}
          >
            {mode === 'login' ? t('w.login') : t('w.register.go')}
          </Button>
        </form>
        {mode === 'register' && <p className="mt-3 text-xs text-slate-600">{t('w.register.bonus')}</p>}
      </Card>

      {accounts.length > 0 && (
        <Card>
          <h3 className="mb-2 font-bold">{t('w.accounts.here')}</h3>
          <ul className="space-y-2">
            {accounts.map((a, index) => (
              <li key={a.phone}>
                <button
                  type="button"
                  className="so-btn-lift flex min-h-12 w-full items-center justify-between rounded-xl border border-slate-300 bg-white px-4 text-left"
                  onClick={() => void quick.run(index)}
                >
                  <span className="font-semibold">{a.name}</span>
                  <span className="text-sm text-slate-600">{a.phone}</span>
                </button>
              </li>
            ))}
          </ul>
          {quick.error && <Problem error={quick.error} />}
        </Card>
      )}

      <Card tone="info">
        <p className="text-sm">{t('w.welcome.twotabs')}</p>
      </Card>
    </>
  )
}
