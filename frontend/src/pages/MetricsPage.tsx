import type { ReactNode } from 'react'
import { calls } from '../api/calls'
import { useAsync } from '../api/hooks'
import { ErrorNotice } from '../components/ErrorNotice'
import { Card, Spinner } from '../components/ui'
import { useI18n } from '../i18n/useI18n'

type Summary = Record<string, unknown>

/** Reads a value from the summary by path; anything missing or not a number/string is undefined. */
function pick(summary: Summary, path: string): unknown {
  let node: unknown = summary
  for (const key of path.split('.')) {
    if (typeof node !== 'object' || node === null) return undefined
    node = (node as Record<string, unknown>)[key]
  }
  return node
}

const num = (summary: Summary, path: string) => {
  const v = pick(summary, path)
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined
}

function statusOf(summary: Summary, section: string): string | undefined {
  const v = pick(summary, `${section}.status`)
  return typeof v === 'string' ? v : undefined
}

function Table({ head, rows, label }: { head: string[]; rows: ReactNode[][]; label: string }) {
  return (
    <div className="overflow-x-auto" role="region" aria-label={label} tabIndex={0}>
      <table className="w-full min-w-[28rem] text-left text-sm" aria-label={label}>
        <thead>
          <tr className="border-b border-slate-300 text-slate-600">
            {head.map((h, i) => (
              <th key={i} className={`py-2 pr-3 font-semibold ${i > 0 ? 'text-right' : ''}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-slate-100">
              {row.map((cell, i) => (
                <td key={i} className={`py-2 pr-3 tabular-nums ${i > 0 ? 'text-right' : ''}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="space-y-3">
      <h3 className="text-lg font-bold">{title}</h3>
      {children}
    </Card>
  )
}

/** Shows the numbers of reports/summary.json exactly; a missing number reads "not measured". */
export function MetricsPage() {
  const { t, num: loc } = useI18n()
  const { data, error, loading } = useAsync(() => calls.metrics(), [])

  if (loading) return <Spinner label={t('common.loading')} />
  if (error) return <ErrorNotice error={error} />
  const summary = (data?.summary ?? null) as Summary | null
  if (!summary) {
    return (
      <Card tone="warn" className="space-y-2">
        <h2 className="text-lg font-bold">{t('metrics.title')}</h2>
        <p>{t('metrics.unavailable')}</p>
        <p className="text-sm text-slate-600">{t('metrics.unavailable.hint')}</p>
      </Card>
    )
  }

  const na = t('metrics.not_measured')
  const pct = (v: number | undefined) => (v === undefined ? na : `${loc((v * 100).toFixed(1))}%`)
  const dec = (v: number | undefined) => (v === undefined ? na : loc(v.toFixed(3)))
  const ms = (v: number | undefined) => (v === undefined ? na : `${loc(v.toFixed(2))} ms`)
  const cnt = (v: number | undefined) => (v === undefined ? na : loc(v))
  const n = (path: string) => num(summary, path)
  const notMeasured = (section: string) =>
    statusOf(summary, section) === undefined || statusOf(summary, section) === 'not_measured'
  const reason = (section: string) => {
    const r = pick(summary, `${section}.reason`)
    return typeof r === 'string' ? r : undefined
  }
  const absent = (section: string) => (
    <p className="rounded-xl bg-slate-100 p-3 text-sm" data-testid={`not-measured-${section}`}>
      <b>{na}</b>
      {reason(section) && <span className="text-slate-600"> — {reason(section)}</span>}
    </p>
  )

  const noisy = 'trust.test_v2.noisy_label'
  const clean = 'trust.test_v2.clean_label'
  const policies: [string, string][] = [
    ['override_default', t('metrics.policy.override_default')],
    ['no_limited_history_band', t('metrics.policy.no_limited_history_band')],
    ['blueprint_literal', t('metrics.policy.blueprint_literal')],
  ]
  const target = n('trust.target_false_positive_rate')

  return (
    <>
      <Card tone="warn" className="space-y-1">
        <h2 className="text-lg font-bold">{t('metrics.title')}</h2>
        <p className="text-sm">{t('metrics.caveat')}</p>
      </Card>

      <Section title={t('metrics.trust')}>
        {notMeasured('trust') ? (
          absent('trust')
        ) : (
          <>
            <p className="text-sm text-slate-600">{t('metrics.trust.about')}</p>
            <Table
              label={t('metrics.trust')}
              head={[t('metrics.metric'), t('metrics.model'), t('metrics.baseline_score'), t('metrics.baseline_rule')]}
              rows={[
                ['PR-AUC', dec(n(`${noisy}.model.pr_auc`)), dec(n(`${noisy}.age_score_baseline.pr_auc`)), '—'],
                ['ROC-AUC', dec(n(`${noisy}.model.roc_auc`)), dec(n(`${noisy}.age_score_baseline.roc_auc`)), '—'],
                [
                  `${t('metrics.recall')}${target === undefined ? '' : ` (${t('metrics.at_fpr', { fpr: pct(target) })})`}`,
                  pct(n(`${noisy}.model.recall_at_target_fpr.recall`)),
                  pct(n(`${noisy}.age_score_baseline.recall_at_target_fpr.recall`)),
                  pct(n(`${noisy}.age_rule_baseline.recall`)),
                ],
                [
                  t('metrics.false_alarm'),
                  pct(n(`${noisy}.model.recall_at_target_fpr.false_positive_rate`)),
                  pct(n(`${noisy}.age_score_baseline.recall_at_target_fpr.false_positive_rate`)),
                  pct(n(`${noisy}.age_rule_baseline.false_positive_rate`)),
                ],
                [t('metrics.ece'), dec(n(`${noisy}.calibration.ece`)), '—', '—'],
              ]}
            />
            <p className="text-sm text-slate-600">
              {t('metrics.clean_label')}: PR-AUC {dec(n(`${clean}.model.pr_auc`))}
            </p>
            <p className="text-sm">
              {t('metrics.latency')}: p95 {ms(n('trust.latency.p95_ms'))}, max {ms(n('trust.latency.max_ms'))} (
              {t('metrics.budget')} {ms(n('trust.latency.budget_ms'))})
            </p>
          </>
        )}
      </Section>

      <Section title={t('metrics.fairness')}>
        {notMeasured('fairness') ? (
          absent('fairness')
        ) : (
          <>
            <p className="text-sm text-slate-600">{t('metrics.fairness.about')}</p>
            <Table
              label={t('metrics.fairness')}
              head={[
                t('metrics.policy'),
                t('metrics.recall'),
                t('metrics.precision_band'),
                t('metrics.fp_new'),
                t('metrics.lh_new'),
              ]}
              rows={policies.map(([key, label]) => {
                const base = `fairness.policies.${key}`
                return [
                  label,
                  pct(n(`${base}.recall_high_risk_overall`)),
                  pct(n(`${base}.precision_of_high_risk_band`)),
                  pct(n(`${base}.false_positive_rate.honest_new`)),
                  pct(n(`${base}.limited_history_share.honest_new`)),
                ]
              })}
            />
          </>
        )}
      </Section>

      <Section title={t('metrics.dispute')}>
        {notMeasured('dispute_classifier') ? (
          absent('dispute_classifier')
        ) : (
          <>
            <p className="text-sm text-slate-600">{t('metrics.dispute.about')}</p>
            <Table
              label={t('metrics.dispute')}
              head={[
                t('metrics.split'),
                t('metrics.cases'),
                t('metrics.stories'),
                t('metrics.macro_f1'),
                t('metrics.accuracy'),
                t('metrics.wrong_refund'),
                t('metrics.wrong_rejection'),
                t('metrics.ece'),
              ]}
              rows={(['validation', 'test1', 'test2'] as const).map((split) => {
                const base = `dispute_classifier.baseline.splits.${split}`
                return [
                  t(`metrics.split.${split}`),
                  cnt(n(`${base}.n`)),
                  cnt(n(`${base}.distinct_stories`)),
                  dec(n(`${base}.macro_f1`)),
                  pct(n(`${base}.accuracy`)),
                  pct(n(`${base}.wrong_refund_rate`)),
                  pct(n(`${base}.wrong_rejection_rate`)),
                  dec(n(`${base}.calibration_ece`)),
                ]
              })}
            />
            <p className="text-sm text-slate-600">{t('metrics.dispute.latency', { ms: ms(n('dispute_classifier.baseline.latency.p95_ms')) })}</p>
          </>
        )}
        {notMeasured('routing') ? (
          absent('routing')
        ) : (
          <>
            <h4 className="font-semibold">{t('metrics.routing')}</h4>
            <Table
              label={t('metrics.routing')}
              head={[
                t('metrics.split'),
                t('metrics.fast_share'),
                t('metrics.fast_accuracy'),
                t('metrics.fast_wrong_refunds'),
                t('metrics.human_share'),
              ]}
              rows={(['test1', 'test2'] as const).map((split) => [
                t(`metrics.split.${split}`),
                pct(n(`routing.${split}.fast_lane_share`)),
                pct(n(`routing.${split}.fast_lane_accuracy`)),
                cnt(n(`routing.${split}.fast_lane_wrong_refunds`)),
                pct(n(`routing.${split}.human_review_share`)),
              ])}
            />
          </>
        )}
      </Section>

      <Section title={t('metrics.injection')}>
        {notMeasured('injection') ? (
          absent('injection')
        ) : (
          <>
            <p className="text-sm text-slate-600">{t('metrics.injection.about')}</p>
            <Table
              label={t('metrics.injection')}
              head={[t('metrics.metric'), t('metrics.value')]}
              rows={[
                [t('metrics.inj.detect_dev'), `${cnt(n('injection.screen.detected'))} / ${cnt(n('injection.screen.injection_phrases'))}`],
                [t('metrics.inj.detect_untuned'), `${cnt(n('injection.untuned_screen.detected'))} / ${cnt(n('injection.untuned_screen.phrases'))}`],
                [t('metrics.inj.false_alarms'), `${cnt(n('injection.screen.false_alarms'))} / ${cnt(n('injection.screen.harmless_phrases'))}`],
                [t('metrics.inj.pairs'), cnt(n('injection.invariance.pairs_checked'))],
                [t('metrics.inj.changed'), cnt(n('injection.invariance.probabilities_changed'))],
                [
                  t('metrics.inj.cls_cases'),
                  `${cnt(n('dispute_classifier.baseline.injection.screen_detected'))} / ${cnt(n('dispute_classifier.baseline.injection.n'))}`,
                ],
                [t('metrics.inj.cls_changed'), cnt(n('dispute_classifier.baseline.injection.pipeline_recommendation_changed'))],
                [t('metrics.inj.cls_human'), cnt(n('dispute_classifier.baseline.injection.human_review_forced'))],
                [t('metrics.inj.held_out'), na],
              ]}
            />
          </>
        )}
      </Section>

      <Section title={t('metrics.time')}>
        {notMeasured('time_study') ? (
          absent('time_study')
        ) : (
          <Table
            label={t('metrics.time')}
            head={[t('metrics.metric'), t('metrics.value')]}
            rows={[
              [t('metrics.time.cases'), cnt(n('time_study.n_cases'))],
              [t('metrics.time.without'), cnt(n('time_study.median_seconds_without_tool'))],
              [t('metrics.time.with'), cnt(n('time_study.median_seconds_with_tool'))],
              [t('metrics.time.saved'), pct(n('time_study.median_time_saved_share'))],
            ]}
          />
        )}
      </Section>
    </>
  )
}
