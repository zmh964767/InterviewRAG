/**
 * SourceCard smoke test
 *
 * 验证组件可正常渲染、展开显示 answer_text。
 */

import { describe, test, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SourceCard } from '@/components/sources/SourceCard'
import type { SourceRef } from '@/lib/types'

const mockSource: SourceRef = {
  question_id: 'q1',
  question_text: '什么是 Transformer?',
  answer_text: 'Transformer 是一种基于自注意力机制的深度学习架构。',
  score: 0.85,
  category: '深度学习',
}

describe('SourceCard', () => {
  test('渲染折叠态：显示编号、分类、题面', () => {
    render(<SourceCard source={mockSource} index={0} />)

    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('深度学习')).toBeInTheDocument()
    expect(screen.getByText('什么是 Transformer?')).toBeInTheDocument()
  })

  test('点击展开显示 answer_text', async () => {
    const user = userEvent.setup()
    render(<SourceCard source={mockSource} index={0} />)

    await user.click(screen.getByText('什么是 Transformer?'))

    expect(screen.getByText(/Transformer 是一种基于自注意力机制/)).toBeInTheDocument()
  })

  test('answer_text 为空时显示占位提示', async () => {
    const sourceNoAnswer = { ...mockSource, answer_text: '' }
    const user = userEvent.setup()
    render(<SourceCard source={sourceNoAnswer} index={0} />)

    await user.click(screen.getByText('什么是 Transformer?'))

    expect(screen.getByText('暂无参考答案')).toBeInTheDocument()
  })
})
