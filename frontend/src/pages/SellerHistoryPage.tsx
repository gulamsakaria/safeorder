import { Link, useParams } from 'react-router-dom'
import { calls } from '../api/calls'
import { useAsync } from '../api/hooks'
import { SnapshotCard } from '../components/analyst'
import { ErrorNotice } from '../components/ErrorNotice'
import { Card, Spinner } from '../components/ui'
import { useI18n } from '../i18n/useI18n'

export function SellerHistoryPage() {
  const { id = '' } = useParams()
  const { t } = useI18n()
  const history = useAsync(() => calls.scoreHistory(id), [id])
  if (history.loading) return <Spinner label={t('common.loading')} />
  if (history.error) return <ErrorNotice error={history.error} onRetry={history.reload} />
  const snapshots = [...(history.data?.snapshots ?? [])].reverse()
  return (
    <>
      <Card>
        <h2 className="text-lg font-bold">
          {t('score.history')}: {id}
        </h2>
        <Link to="/analyst" className="text-blue-800 underline">
          {t('case.back')}
        </Link>
      </Card>
      {snapshots.length === 0 && (
        <Card tone="info">
          <p>{t('score.history.empty')}</p>
        </Card>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {snapshots.map((s) => (
          <SnapshotCard key={s.id} snapshot={s} heading={`#${s.id}`} />
        ))}
      </div>
    </>
  )
}
