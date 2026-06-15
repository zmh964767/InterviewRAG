/**
 * ChatInput smoke test
 *
 * 验证组件可正常渲染，不崩溃。
 */

import { describe, test, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatInput } from '@/components/chat/ChatInput'

describe('ChatInput', () => {
  test('渲染输入框和推荐问题', () => {
    render(<ChatInput onSend={vi.fn()} isLoading={false} />)

    expect(screen.getByPlaceholderText('输入你的面试问题...')).toBeInTheDocument()
    expect(screen.getByText('Transformer 自注意力机制')).toBeInTheDocument()
    expect(screen.getByText('RAG 的基本流程')).toBeInTheDocument()
  })

  test('点击推荐问题填入输入框', async () => {
    const user = userEvent.setup()
    render(<ChatInput onSend={vi.fn()} isLoading={false} />)

    await user.click(screen.getByText('RAG 的基本流程'))

    expect(screen.getByPlaceholderText('输入你的面试问题...')).toHaveValue('RAG 的基本流程')
  })

  test('loading 时显示停止按钮', () => {
    render(<ChatInput onSend={vi.fn()} isLoading={true} />)

    expect(screen.getByLabelText('停止生成')).toBeInTheDocument()
  })
})
