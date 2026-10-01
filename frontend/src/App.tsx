import { Link, Route, Routes } from 'react-router-dom'
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
      <Route element={<Layout />}>
        <Route index element={<TrustCheckPage />} />
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
