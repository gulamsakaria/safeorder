import { Link, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Card } from './components/ui'
import { useI18n } from './i18n/useI18n'
import { DemoPage } from './pages/DemoPage'
import { DisputePage } from './pages/DisputePage'
import { OrderPage } from './pages/OrderPage'
import { ReportProblemPage } from './pages/ReportProblemPage'
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
        <Route path="demo" element={<DemoPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
