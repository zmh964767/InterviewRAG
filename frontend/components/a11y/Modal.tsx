'use client'

import { useEffect, useId, useRef } from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  /**
   * 标题文本。Modal 内部默认渲染为 <h2 id={titleId}>{title}</h2>,
   * 与 aria-labelledby 关联。
   * 提供 `titleNode` 时改用自定义节点(此时 title 作为 aria-label 兜底)。
   */
  title: string
  closeOnBackdropClick?: boolean
  widthClassName?: string
  /**
   * 自定义标题节点(如 IngestModal 的 h3 + 关闭 X 按钮 header)。
   * 提供时 Modal 不渲染默认 h2;aria 关联用 aria-label={title}。
   */
  titleNode?: React.ReactNode
  children: React.ReactNode
}

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * 轻量模态对话框
 *
 * 提供: backdrop + dialog 包裹层;role="dialog" + aria-modal + aria-labelledby;
 * 焦点陷阱(优先用 HTMLElement.prototype.inert 隔离外部,不支持时回退到
 * 内部 Tab 循环);Escape 关闭;打开/关闭时焦点恢复。
 *
 * 零依赖,纯原生 API。
 */
export function Modal({
  open,
  onClose,
  title,
  closeOnBackdropClick = true,
  widthClassName = 'w-[28rem] max-w-[90vw]',
  titleNode,
  children,
}: ModalProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement | null>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)

  // 进入时聚焦首个可聚焦元素;关闭时还原焦点。
  useEffect(() => {
    if (open) {
      previouslyFocusedRef.current = document.activeElement as HTMLElement | null
      const raf = requestAnimationFrame(() => {
        const dialog = dialogRef.current
        if (!dialog) return
        const first = dialog.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
        if (first) {
          first.focus()
        } else {
          dialog.focus()
        }
      })
      return () => cancelAnimationFrame(raf)
    }
    // 关闭时还原焦点
    previouslyFocusedRef.current?.focus()
    return undefined
  }, [open])

  // 焦点陷阱:对 dialog 的同级节点设 inert(特性支持时);不支持时回退到内部 Tab 循环。
  useEffect(() => {
    if (!open) return
    const dialog = dialogRef.current
    if (!dialog) return

    const inertSupported = 'inert' in HTMLElement.prototype

    if (inertSupported) {
      // 找出 dialog 的所有兄弟节点,设 inert;记录原值以便还原。
      const parent = dialog.parentElement
      if (!parent) return
      const siblings = Array.from(parent.children).filter(
        (el) => el !== dialog,
      ) as HTMLElement[]
      const originals = siblings.map((el) => el.hasAttribute('inert'))
      siblings.forEach((el) => el.setAttribute('inert', ''))
      return () => {
        siblings.forEach((el, i) => {
          if (!originals[i]) el.removeAttribute('inert')
        })
      }
    }

    // 回退:内部 Tab 循环
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !dialogRef.current) return
      const focusables = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      )
      if (focusables.length === 0) {
        e.preventDefault()
        return
      }
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement as HTMLElement | null
      if (e.shiftKey) {
        if (active === first || !dialogRef.current.contains(active)) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (active === last || !dialogRef.current.contains(active)) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])

  // Escape 关闭(只读 escape 键,且排除 IME composition)
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      // 仅在非 IME 组合状态下响应,避免打断中文输入
      if (e.isComposing) return
      onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(26, 22, 18, 0.3)', backdropFilter: 'blur(4px)' }}
      onClick={closeOnBackdropClick ? onClose : undefined}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleNode ? undefined : titleId}
        aria-label={titleNode ? title : undefined}
        className={`p-6 rounded-2xl animate-slide-up ${widthClassName}`}
        style={{
          background: 'var(--paper)',
          border: '1px solid var(--border)',
          boxShadow: 'var(--shadow-lg)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {titleNode ?? (
          <h2
            id={titleId}
            className="text-base font-semibold mb-2"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}
          >
            {title}
          </h2>
        )}
        {children}
      </div>
    </div>
  )
}
