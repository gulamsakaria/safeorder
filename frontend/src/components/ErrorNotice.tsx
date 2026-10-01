import { ApiProblem } from '../api/client'
import { useI18n } from '../i18n/useI18n'
import { Button, Card } from './ui'

/** A readable, translated message for an API error, with an optional retry. */
export function ErrorNotice({ error, onRetry }: { error: ApiProblem; onRetry?: () => void }) {
  const { t, has } = useI18n()
  const key = `common.error.${error.code}`
  return (
    <Card tone="danger" role="alert">
      <p className="font-semibold text-red-900">{has(key) ? t(key) : t('common.error.generic')}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-3" onClick={onRetry}>
          {t('common.retry')}
        </Button>
      )}
    </Card>
  )
}
