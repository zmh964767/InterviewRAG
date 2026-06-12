'use client'

import type { CSSProperties } from 'react'

interface SkeletonProps {
  className?: string
  rounded?: 'sm' | 'md' | 'lg' | 'full'
}

const ROUND_MAP: Record<NonNullable<SkeletonProps['rounded']>, string> = {
  sm: 'rounded',
  md: 'rounded-md',
  lg: 'rounded-lg',
  full: 'rounded-full',
}

/**
 * 轻量 shimmer 占位组件
 * - 复用 globals.css 已定义的 shimmer 关键帧(无需重写)
 * - prefers-reduced-motion 由 globals.css 媒体查询统一关闭 animation
 */
export function Skeleton({ className = '', rounded = 'md' }: SkeletonProps) {
  const style: CSSProperties = {
    background:
      'linear-gradient(90deg, var(--border-subtle) 0%, var(--border) 50%, var(--border-subtle) 100%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite linear',
  }
  return (
    <span
      aria-hidden="true"
      className={`inline-block align-middle ${ROUND_MAP[rounded]} ${className}`}
      style={style}
    />
  )
}
