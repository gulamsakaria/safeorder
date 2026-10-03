import { Link, Route, Routes } from 'react-router-dom'
import { WALLET } from './api/client'
import { Layout } from './components/Layout'
import { Card } from './components/ui'
import { useI18n } from './i18n/useI18n'
import { AnalystCasePage } from './pages/AnalystCasePage'
import { AnalystQueuePage } from './pages/AnalystQueuePage'
import { DemoPage } from './pages/DemoPage'
import { MetricsPage } from './pages/MetricsPage'
import { DisputePage } from './pages/DisputePage'
import { OrderPage } from './pages/OrderPage'
import { ReportProblemPage } from './pages/ReportProblemPage'
import { SellerHistoryPage } from './pages/SellerHistoryPage'
import { TrustCheckPage } from './pages/TrustCheckPage'
import { AccountPage } from './wallet/pages/AccountPage'
import { AdminPage } from './wallet/pages/AdminPage'
import { GuidePage } from './wallet/pages/GuidePage'
import { LandingPage } from './wallet/pages/LandingPage'
import { HistoryPage } from './wallet/pages/HistoryPage'
import { HomePage } from './wallet/pages/HomePage'
import { MorePage } from './wallet/pages/MorePage'
import { PayPage } from './wallet/pages/PayPage'
import { SellerHubPage } from './wallet/pages/SellerHubPage'
import { WalletOrderPage } from './wallet/pages/WalletOrderPage'
import { WelcomePage } from './wallet/pages/WelcomePage'
import { WalletShell } from './wallet/WalletShell'

function NotFound() {
  const { t } = useI18n()
  return (
    <Card tone="warn">
      <p className="mb-3">{t('common.error.NOT_FOUND')}</p>
      <Link className="font-semibold text-blue-800 underline" to="/">
        {t('common.back')}
      </Link>
    </Card>
  )
}

export default function App() {
  return (
    <Routes>
      {WALLET && <Route index element={<LandingPage />} />}
      {WALLET && (
        <Route element={<WalletShell />}>
          <Route path="welcome" element={<WelcomePage />} />
          <Route path="home" element={<HomePage />} />
          <Route path="pay" element={<PayPage />} />
          <Route path="account" element={<AccountPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="more" element={<MorePage />} />
          <Route path="seller" element={<SellerHubPage />} />
          <Route path="orders/:id" element={<WalletOrderPage />} />
          <Route path="admin" element={<AdminPage />} />
          <Route path="guide" element={<GuidePage />} />
        </Route>
      )}
      <Route element={<Layout />}>
        {WALLET ? <Route path="check" element={<TrustCheckPage />} /> : <Route index element={<TrustCheckPage />} />}
        <Route path="order/:id" element={<OrderPage />} />
        <Route path="order/:id/report" element={<ReportProblemPage />} />
        <Route path="dispute/:id" element={<DisputePage />} />
        <Route path="analyst" element={<AnalystQueuePage />} />
        <Route path="analyst/dispute/:id" element={<AnalystCasePage />} />
        <Route path="analyst/seller/:id" element={<SellerHistoryPage />} />
        <Route path="metrics" element={<MetricsPage />} />
        <Route path="demo" element={<DemoPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
