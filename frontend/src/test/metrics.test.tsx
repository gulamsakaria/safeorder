import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../mocks/server'
import { renderApp } from './render'

const SUMMARY = JSON.parse(readFileSync(resolve(__dirname, '../../../reports/summary.json'), 'utf8'))
const BN = '০১২৩৪৫৬৭৮৯'
const bn = (text: string) => text.replace(/\d/g, (d) => BN[Number(d)])

function serve(summary: unknown) {
  server.use(
    http.get('*/api/metrics/summary', () =>
      HttpResponse.json({ available: summary !== null, summary, reports: {} }),
    ),
  )
}

describe('metrics page', () => {
  it('shows the numbers of reports/summary.json exactly', async () => {
    serve(SUMMARY)
    renderApp('/metrics', 'bn')
    const trust = within(await screen.findByRole('table', { name: 'বিক্রেতার ট্রাস্ট মডেল' }))
    const noisy = SUMMARY.trust.test_v2.noisy_label
    expect(trust.getByText(bn(noisy.model.pr_auc.toFixed(3)))).toBeInTheDocument()
    expect(trust.getByText(bn(noisy.age_score_baseline.pr_auc.toFixed(3)))).toBeInTheDocument()
    expect(trust.getByText(bn(`${(noisy.model.recall_at_target_fpr.recall * 100).toFixed(1)}%`))).toBeInTheDocument()

    const fairness = within(screen.getByRole('table', { name: 'ন্যায্যতা: নতুন সৎ বিক্রেতা' }))
    const literal = SUMMARY.fairness.policies.blueprint_literal.recall_high_risk_overall
    expect(fairness.getByText(bn(`${(literal * 100).toFixed(1)}%`))).toBeInTheDocument()
  })

  it('shows the dispute classifier numbers exactly, with the one-author caveat', async () => {
    serve(SUMMARY)
    renderApp('/metrics', 'bn')
    const table = within(await screen.findByRole('table', { name: 'অভিযোগ শ্রেণিবিন্যাস ও রুটিং' }))
    const test1 = SUMMARY.dispute_classifier.baseline.splits.test1
    expect(table.getByText(bn(test1.macro_f1.toFixed(3)))).toBeInTheDocument()
    expect(table.getByText(bn(`${(test1.wrong_refund_rate * 100).toFixed(1)}%`))).toBeInTheDocument()
    expect(screen.getByText(/সব স্প্লিটের লেখক একজন/)).toBeInTheDocument()
  })

  it('says "not measured" for the dispute sections when their reports are missing', async () => {
    const partial = structuredClone(SUMMARY)
    partial.dispute_classifier = { status: 'not_measured', reason: 'no model' }
    partial.routing = { status: 'not_measured', reason: 'no model' }
    serve(partial)
    renderApp('/metrics', 'en')
    expect(await screen.findByTestId('not-measured-dispute_classifier')).toHaveTextContent('not measured')
    expect(screen.getByTestId('not-measured-routing')).toHaveTextContent('not measured')
  })

  it('says "not measured" for sections without a report, with the reason', async () => {
    serve(SUMMARY)
    renderApp('/metrics', 'en')
    for (const section of ['time_study']) {
      const box = await screen.findByTestId(`not-measured-${section}`)
      expect(box).toHaveTextContent('not measured')
      expect(box).toHaveTextContent(SUMMARY[section].reason)
    }
  })

  it('a missing number inside a measured section reads "not measured", never a made-up value', async () => {
    const partial = structuredClone(SUMMARY)
    delete partial.trust.test_v2.noisy_label.model.pr_auc
    serve(partial)
    renderApp('/metrics', 'en')
    const row = (await screen.findByRole('row', { name: /^PR-AUC/ })) as HTMLElement
    expect(within(row).getAllByRole('cell')[1]).toHaveTextContent('not measured')
  })

  it('shows an empty state when no report exists', async () => {
    serve(null)
    renderApp('/metrics', 'bn')
    expect(await screen.findByText('মূল্যায়ন রিপোর্ট এখনও তৈরি হয়নি।')).toBeInTheDocument()
  })
})
