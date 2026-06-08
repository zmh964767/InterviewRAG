'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { listQuestions } from '@/lib/api'
import type { Question, QuestionListResponse } from '@/lib/types'

interface UseKnowledgeBaseResult {
  items: Question[]
  total: number
  page: number
  size: number
  categories: string[]
  isLoading: boolean
  error: string | null
  filters: { q: string; category: string; difficulty: string }
  setQ: (q: string) => void
  setCategory: (c: string) => void
  setDifficulty: (d: string) => void
  setPage: (p: number) => void
  refresh: () => void
  removeItem: (id: string) => void
  insertItem: (q: Question) => void
}

const DEFAULT_SIZE = 20
const SEARCH_DEBOUNCE_MS = 300

export function useKnowledgeBase(): UseKnowledgeBaseResult {
  const [items, setItems] = useState<Question[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(DEFAULT_SIZE)
  const [categories, setCategories] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [q, setQInternal] = useState('')
  const [category, setCategory] = useState('')
  const [difficulty, setDifficulty] = useState('')

  // 搜索框 300ms debounce
  const [qDebounced, setQDebounced] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const setQ = useCallback((value: string) => {
    setQInternal(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setQDebounced(value)
    }, SEARCH_DEBOUNCE_MS)
  }, [])

  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    },
    [],
  )

  const filters = { q, category, difficulty }

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res: QuestionListResponse = await listQuestions({
        page,
        size,
        q: qDebounced,
        category,
        difficulty,
      })
      setItems(res.items)
      setTotal(res.total)
      setCategories(res.categories)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setIsLoading(false)
    }
  }, [page, size, qDebounced, category, difficulty])

  useEffect(() => {
    void load()
  }, [load])

  // 过滤变化时回到第 1 页
  useEffect(() => {
    setPage(1)
  }, [qDebounced, category, difficulty])

  const refresh = useCallback(() => {
    void load()
  }, [load])

  const removeItem = useCallback((id: string) => {
    setItems((prev) => prev.filter((q) => q.id !== id))
    setTotal((prev) => Math.max(0, prev - 1))
  }, [])

  const insertItem = useCallback((q: Question) => {
    setItems((prev) => [q, ...prev])
    setTotal((prev) => prev + 1)
  }, [])

  return {
    items,
    total,
    page,
    size,
    categories,
    isLoading,
    error,
    filters,
    setQ,
    setCategory,
    setDifficulty,
    setPage,
    refresh,
    removeItem,
    insertItem,
  }
}
