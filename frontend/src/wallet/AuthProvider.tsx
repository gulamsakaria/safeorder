import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Schemas } from '../api/client'
import { wallet } from './calls'
import {
  type RememberedAccount,
  forgetAccount,
  getToken,
  listAccounts,
  rememberAccount,
  setToken,
} from './session'

type Me = Schemas['MeOut']

interface Auth {
  me: Me | null
  /** false until the first check of a stored token has finished */
  ready: boolean
  accounts: RememberedAccount[]
  signIn: (phone: string, pin: string) => Promise<void>
  signUp: (name: string, phone: string, pin: string) => Promise<void>
  signOut: () => Promise<void>
  switchTo: (account: RememberedAccount) => Promise<void>
  refresh: () => Promise<void>
  setMe: (me: Me) => void
}

const AuthContext = createContext<Auth | null>(null)

export function useAuth(): Auth {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [ready, setReady] = useState(false)
  const [accounts, setAccounts] = useState<RememberedAccount[]>(listAccounts)

  const load = useCallback(async () => {
    if (!getToken()) {
      setMe(null)
      return
    }
    try {
      setMe(await wallet.me())
    } catch {
      setToken(null) // expired, signed out elsewhere, or frozen
      setMe(null)
    }
  }, [])

  useEffect(() => {
    void load().finally(() => setReady(true))
  }, [load])

  const finish = useCallback((token: string, user: Me) => {
    setToken(token)
    rememberAccount({ phone: user.phone, name: user.name, token })
    setAccounts(listAccounts())
    setMe(user)
  }, [])

  const value = useMemo<Auth>(
    () => ({
      me,
      ready,
      accounts,
      signIn: async (phone, pin) => {
        const out = await wallet.login({ phone, pin })
        finish(out.token, out.user)
      },
      signUp: async (name, phone, pin) => {
        const out = await wallet.register({ name, phone, pin })
        finish(out.token, out.user)
      },
      signOut: async () => {
        const phone = me?.phone
        try {
          await wallet.logout()
        } catch {
          // the token is dropped here in any case
        }
        if (phone) forgetAccount(phone)
        setAccounts(listAccounts())
        setToken(null)
        setMe(null)
      },
      switchTo: async (account) => {
        setToken(account.token)
        try {
          setMe(await wallet.me())
        } catch (e) {
          forgetAccount(account.phone)
          setAccounts(listAccounts())
          setToken(null)
          setMe(null)
          throw e
        }
      },
      refresh: load,
      setMe,
    }),
    [me, ready, accounts, finish, load],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
