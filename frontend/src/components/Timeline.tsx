import type { Schemas } from '../api/client'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime } from '../lib/format'

export function Timeline({ events }: { events: Schemas['TimelineEventOut'][] }) {
  const { t, has, lang } = useI18n()
  return (
    <ol className="space-y-3 border-l-2 border-slate-300 pl-4">
      {events.map((event, index) => (
        <li key={`${event.t}-${event.event}-${index}`}>
          <p className="font-semibold">
            {has(`event.${event.event}`) ? t(`event.${event.event}`) : event.event}
          </p>
          <p className="text-sm text-slate-600">{formatDateTime(event.t, lang)}</p>
        </li>
      ))}
    </ol>
  )
}
