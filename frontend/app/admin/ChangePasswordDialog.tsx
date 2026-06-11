'use client'

import { useState, useCallback } from 'react'
import { adminChangePassword } from '@/lib/api'

interface ChangePasswordDialogProps {
  isOpen: boolean
  onClose: () => void
}

export function ChangePasswordDialog({ isOpen, onClose }: ChangePasswordDialogProps) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)

    if (!currentPassword || !newPassword || !confirmPassword) {
      setError('请填写所有字段')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致')
      return
    }
    if (newPassword.length < 6) {
      setError('新密码至少 6 个字符')
      return
    }
    if (newPassword === currentPassword) {
      setError('新密码不能与当前密码相同')
      return
    }

    setLoading(true)
    try {
      const result = await adminChangePassword(currentPassword, newPassword)
      setSuccess(result.message)
      // 成功后清空字段，3 秒后自动关闭
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => {
        onClose()
        setSuccess(null)
      }, 2500)
    } catch (e) {
      setError(e instanceof Error ? e.message : '修改失败')
    } finally {
      setLoading(false)
    }
  }, [currentPassword, newPassword, confirmPassword, onClose])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(26, 22, 18, 0.3)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        className="w-96 p-6 rounded-2xl"
        style={{ background: 'var(--paper)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-lg)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          className="text-lg font-semibold mb-5"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}
        >
          修改密码
        </h2>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--ink-muted)' }}>当前密码</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
              autoFocus
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--ink-muted)' }}>新密码（至少 6 个字符）</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--ink-muted)' }}>确认新密码</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
              disabled={loading}
            />
          </div>

          {error && (
            <p className="text-xs" style={{ color: 'var(--accent)' }}>{error}</p>
          )}
          {success && (
            <p className="text-xs" style={{ color: 'var(--success)' }}>{success}</p>
          )}

          <div className="flex gap-2 justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm rounded-lg transition-colors"
              style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm font-medium rounded-lg transition-all disabled:opacity-50"
              style={{ background: 'var(--ink)', color: 'var(--cream)' }}
            >
              {loading ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
