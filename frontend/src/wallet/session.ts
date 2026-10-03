// The signed-in account of this browser tab, and the accounts remembered in this browser.
// The active token lives in sessionStorage, so two tabs can be two different people (a buyer in one
// tab, a seller in another). Remembered accounts live in localStorage so a tab can switch quickly.

const ACTIVE_KEY = 'safeorder.token'
const ACCOUNTS_KEY = 'safeorder.accounts'

export interface RememberedAccount {
  phone: string
  name: string
  token: string
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(ACTIVE_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(ACTIVE_KEY, token)
    else sessionStorage.removeItem(ACTIVE_KEY)
  } catch {
    // storage blocked: the person will have to sign in again after a reload
  }
}

export function listAccounts(): RememberedAccount[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(ACCOUNTS_KEY) ?? '[]')
    return Array.isArray(parsed) ? (parsed as RememberedAccount[]) : []
  } catch {
    return []
  }
}

function saveAccounts(accounts: RememberedAccount[]): void {
  try {
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts))
  } catch {
    // ignore: the list just will not be remembered
  }
}

export function rememberAccount(account: RememberedAccount): void {
  saveAccounts([...listAccounts().filter((a) => a.phone !== account.phone), account])
}

export function forgetAccount(phone: string): void {
  saveAccounts(listAccounts().filter((a) => a.phone !== phone))
}
