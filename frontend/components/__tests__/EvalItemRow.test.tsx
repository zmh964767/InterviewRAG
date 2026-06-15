/**
 * EvalItemRow smoke test
 *
 * 验证组件可正常渲染，不崩溃。
 */

import { describe, test, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EvalItemRow } from '@/components/eval/EvalItemRow'
import type { EvalItemResult } from '@/lib/types'

const mockItem: EvalItemResult = {
  id: 'eval1',
  question: '什么是 RAG?',
  answer: '检索增强生成是一种...',
  metrics: {
    faithfulness: 0.9,
    answer_relevancy: 0.85,
    context_precision: 0.7,
    context_recall: 0.65,
  },
}

describe('EvalItemRow', () => {
  test('渲染折叠态：显示题面和指标', () => {
    render(<EvalItemRow item={mockItem} index={0} />)

    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('什么是 RAG?')).toBeInTheDocument()
    expect(screen.getByText(/F 90\.0%/)).toBeInTheDocument()
  })

  test('点击展开显示详情', async () => {
    const user = userEvent.setup()
    render(<EvalItemRow item={mockItem} index={0} />)

    await user.click(screen.getByText('什么是 RAG?'))

    expect(screen.getByText('指标')).toBeInTheDocument()
    expect(screen.getByText('生成的答案')).toBeInTheDocument()
    expect(screen.getByText(/检索增强生成/)).toBeInTheDocument()
  })

  test('渲染错误状态', () => {
    const errorItem: EvalItemResult = {
      ...mockItem,
      error: 'RAG 查询超时',
      metrics: {},
    }
    render(<EvalItemRow item={errorItem} index={0} />)

    // 不崩溃即可
    expect(screen.getByText('什么是 RAG?')).toBeInTheDocument()
  })
})
