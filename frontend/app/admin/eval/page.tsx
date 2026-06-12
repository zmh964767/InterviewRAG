'use client'

import { useState, useEffect, useCallback } from 'react'
import { RagMetricsBar } from '@/components/eval/RagMetricsBar'
import { ComparisonTable } from '@/components/eval/ComparisonTable'
import { EvalItemRow } from '@/components/eval/EvalItemRow'
import { RunEvalButton } from '@/components/eval/RunEvalButton'
import { EvalCompareView } from '@/components/eval/EvalCompareView'
import { Skeleton } from '@/components/ui/Skeleton'
import { adminGetEvalSummary, adminGetEvalDetail } from '@/lib/api'
import { EVAL } from '@/lib/copy'
import type { EvalSummaryResponse, EvalDetailResponse } from '@/lib/types'

type Tab = 'overview' | 'items' | 'history' | 'compare'

export default function AdminEvalPage() {
  const [summary, setSummary] = useState<EvalSummaryResponse | null>(null)
  const [latestDetail, setLatestDetail] = useState<EvalDetailResponse | null>(null)
  const [expandedTs, setExpandedTs] = useState<string | null>(null)
  const [expandedDetail, setExpandedDetail] = useState<EvalDetailResponse | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('overview')

  const load = useCallback(async () => {
    try {
      const s = await adminGetEvalSummary()
      setSummary(s)
      if (s.latest) {
        try {
          const d = await adminGetEvalDetail()
          setLatestDetail(d)
        } catch {
          setLatestDetail(null)
        }
      } else {
        setLatestDetail(null)
      }
    } catch {
      setError(EVAL.LOAD_ERROR)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const handleExpand = async (key: string, ts: string) => {
    if (expandedTs === key) { setExpandedTs(null); setExpandedDetail(null); return }
    setExpandedTs(key)
    setDetailLoading(true)
    try { setExpandedDetail(await adminGetEvalDetail(ts)) }
    catch { setExpandedDetail(null) }
    finally { setDetailLoading(false) }
  }

  const formatTs = (ts: string) => {
    if (!ts) return ''
    const normalized = ts.replace(/T(\d{2})-(\d{2})-(\d{2})/, 'T$1:$2:$3')
    const d = new Date(normalized)
    return isNaN(d.getTime()) ? ts : d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  const latest = summary?.latest
  const sortedItems = latestDetail?.items
    ? [...latestDetail.items].sort((a, b) => (a.metrics.faithfulness ?? 0) - (b.metrics.faithfulness ?? 0))
    : []

  return (
    <div className="flex flex-col h-full">
      <header
        className="h-14 px-6 flex items-center gap-4 shrink-0 border-b"
        style={{ borderColor: 'var(--border)', background: 'rgba(250, 248, 245, 0.8)' }}
      >
        <h1 className="text-lg font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
          {EVAL.TITLE}
        </h1>
        {latest && <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>{EVAL.LAST_RUN(formatTs(latest.timestamp))}</span>}
        <div className="flex-1" />
        <RunEvalButton onComplete={() => void load()} />
      </header>

      {/* Tabs */}
      <div className="px-6 pt-3 flex gap-1 border-b" style={{ borderColor: 'var(--border)' }}>
        {([
          ['overview', '概览'],
          ['items', '题目详情'],
          ['history', EVAL.HISTORY_TITLE],
          ['compare', '对比'],
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className="px-4 py-2 text-sm rounded-t-lg"
            style={{
              background: tab === key ? 'var(--paper)' : 'transparent',
              color: tab === key ? 'var(--ink)' : 'var(--ink-muted)',
              borderBottom: tab === key ? '2px solid var(--ink)' : '2px solid transparent',
            }}
          >
            {label}
            {key === 'items' && sortedItems.length > 0 && (
              <span className="ml-1.5 text-xs" style={{ color: 'var(--ink-muted)' }}>({sortedItems.length})</span>
            )}
            {key === 'history' && (summary?.history.length ?? 0) > 0 && (
              <span className="ml-1.5 text-xs" style={{ color: 'var(--ink-muted)' }}>({summary?.history.length})</span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {error && <div className="p-4 rounded-xl mb-6" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b' }}>{error}</div>}

        {tab === 'overview' && (
          <>
            {!summary && !error && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                <div className="rounded-xl p-5" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
                  <Skeleton className="h-4 w-24 mb-4" />
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full mb-2" />
                  ))}
                </div>
                <div className="rounded-xl p-5" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
                  <Skeleton className="h-4 w-24 mb-4" />
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full mb-2" />
                  ))}
                </div>
              </div>
            )}
            {summary && !latest && <div className="text-center py-12"><p className="text-sm" style={{ color: 'var(--ink-muted)' }}>{EVAL.EMPTY}</p></div>}

            {latest && (
              <>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                  <div className="rounded-xl p-5" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
                    <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}>{EVAL.RAGAS_TITLE}</h2>
                    <RagMetricsBar metrics={latest.metrics} />
                  </div>
                  {latestDetail && (
                    <div className="rounded-xl p-5" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
                      <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}>{EVAL.COMPARISON_TITLE}</h2>
                      <ComparisonTable comparison={latestDetail.comparison} />
                    </div>
                  )}
                </div>

                <div className="flex gap-4 mb-8">
                  {[
                    [EVAL.TOTAL_QUESTIONS, latest.total],
                    [EVAL.ERROR_COUNT, latest.error_count],
                  ].map(([label, val]) => (
                    <div key={label} className="rounded-xl px-5 py-3" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
                      <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>{label} </span>
                      <span className="text-sm font-medium tabular-nums" style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}>{val}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {tab === 'items' && (
          <div>
            {sortedItems.length === 0 ? (
              <p className="text-center py-12 text-sm" style={{ color: 'var(--ink-muted)' }}>
                {latest ? '暂无题目数据' : '请先运行评估'}
              </p>
            ) : (
              <div className="rounded-xl overflow-hidden" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
                <div className="px-4 py-2 text-xs flex items-center gap-3" style={{ color: 'var(--ink-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span>按 faithfulness 升序排列</span>
                  <span className="ml-auto">F = Faithfulness, R = Answer Relevancy</span>
                </div>
                {sortedItems.map((item, i) => (
                  <EvalItemRow key={item.id} item={item} index={i} />
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'history' && (
          <div>
            {summary && summary.history.length > 0 ? (
              <div className="space-y-2">
                {summary.history.map((snap, idx) => (
                  <div key={`${snap.timestamp}-${idx}`} className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border-subtle)' }}>
                    <button
                      className="w-full flex items-center justify-between px-5 py-3 text-left transition-colors"
                      style={{ background: expandedTs === `${snap.timestamp}-${idx}` ? 'var(--cream)' : 'var(--paper)' }}
                      onClick={() => handleExpand(`${snap.timestamp}-${idx}`, snap.timestamp)}
                    >
                      <div className="flex items-center gap-4">
                        <span className="text-xs font-medium" style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}>{formatTs(snap.timestamp)}</span>
                        <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>{snap.total} 题</span>
                        <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>错误 {snap.error_count}</span>
                      </div>
                      <svg className="w-4 h-4 transition-transform" style={{ color: 'var(--ink-muted)', transform: expandedTs === snap.timestamp ? 'rotate(180deg)' : 'rotate(0deg)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                      </svg>
                    </button>
                    {expandedTs === `${snap.timestamp}-${idx}` && (
                      <div className="px-5 pb-4" style={{ background: 'var(--cream)' }}>
                        {detailLoading ? (
                          <p className="text-xs py-2" style={{ color: 'var(--ink-muted)' }}>{EVAL.LOAD_DETAIL}</p>
                        ) : expandedDetail ? (
                          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2">
                            <div>
                              <h3 className="text-xs font-medium mb-2" style={{ color: 'var(--ink-muted)' }}>{EVAL.RAGAS_TITLE}</h3>
                              <RagMetricsBar metrics={expandedDetail.aggregated} compact />
                            </div>
                            <div>
                              <h3 className="text-xs font-medium mb-2" style={{ color: 'var(--ink-muted)' }}>{EVAL.COMPARISON_TITLE}</h3>
                              <ComparisonTable comparison={expandedDetail.comparison} compact />
                            </div>
                          </div>
                        ) : (
                          <p className="text-xs py-2" style={{ color: 'var(--ink-muted)' }}>{EVAL.LOAD_DETAIL_FAILED}</p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center py-12 text-sm" style={{ color: 'var(--ink-muted)' }}>暂无历史快照</p>
            )}
          </div>
        )}

        {tab === 'compare' && (
          <div>
            {!summary ? (
              <p className="text-center py-12 text-sm" style={{ color: 'var(--ink-muted)' }}>加载中…</p>
            ) : !summary.latest && summary.history.length === 0 ? (
              <p className="text-center py-12 text-sm" style={{ color: 'var(--ink-muted)' }}>暂无评估快照,请先运行评估</p>
            ) : (
              <EvalCompareView history={summary.history} latest={summary.latest} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
