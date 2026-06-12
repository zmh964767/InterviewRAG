/**
 * 前端文案集中地
 *
 * 设计目的：
 * - 把分散在各组件里的高频中文文案抽到一个文件，方便未来引入 i18n 库
 *   (例如 next-intl) 时只换 dictionary loader 即可，无需大规模改业务代码。
 * - 一次性文案(标题/段落/侧栏 nav/表格表头)保持原样,避免回归。
 *
 * 使用规范:
 * - 高频复用(按钮、placeholder、aria-label、错误条) -> 抽常量
 * - 一次性展示(欢迎语、空态描述) -> 留在组件内
 *
 * 颜色/形状规则(待后续 commit 沉淀):
 * - 主操作(确认/登录/开始) = `--ink`
 * - 品牌/重要 CTA(新建对话/主要操作) = `--accent`
 * - 危险操作(删除/退出) = `--accent` + 红色文字
 * - 圆角收敛到 3 档: sm=6px / md=10px / lg=16px
 */

export const CHAT = {
  ARIA: {
    SEND: '发送',
    STOP: '停止生成',
    DISMISS_ERROR: '关闭错误提示',
  },
  PLACEHOLDER: {
    IDLE: '输入你的面试问题...',
    STREAMING: 'AI 正在回答中，你可以提前编辑下一个问题...',
  },
  ERROR: {
    ABORTED: '生成已停止',
    FAILED: '生成出错了',
    RETRY: '重新生成',
    DISMISS: '关闭',
  },
} as const

/** 通用状态文案(加载/空/重试) */
export const STATE = {
  LOADING: '加载中',
  EMPTY: '暂无数据',
  RETRY: '重试',
  DISMISS: '关闭',
} as const

/** 管理端高频文案 */
export const ADMIN = {
  STATS: {
    TOTAL_QUESTIONS: '题目总数',
    CATEGORY_COUNT: '分类数',
    LATEST_RELEVANCY: '最近评估 Answer Relevancy',
  },
  CATEGORIES_TITLE: '分类统计',
  EMPTY_CATEGORIES: '暂无分类数据',
  RETRY_STATS: '统计加载失败',
  RETRY_EVAL: '评估概览加载失败',
  ALERTS: {
    DELETE_FAILED: '删除失败',
    UNDO_FAILED: '撤销失败，该题已存在',
  },
} as const

/** 可访问性文案(skip link / aria-label) */
export const A11Y = {
  SKIP_TO_MAIN: '跳到主要内容',
  CLOSE: '关闭',
  CLOSE_DIALOG: '关闭对话框',
  MENU: '打开/关闭侧边栏',
  DIALOG_OPENED: '对话框已打开，按 Escape 关闭',
  NEW_CHAT: '新建对话',
  DELETE_CONVERSATION: '删除对话',
  SWITCH_TO_CONVERSATIONS: '切换到对话',
  SWITCH_TO_QUESTIONS: '切换到题目库',
} as const

/** 题目库高频文案 */
export const QUESTIONS = {
  TITLE: '题目库',
  TOTAL: (n: number) => `共 ${n} 题`,
  SEARCH_PLACEHOLDER: '搜索题面或答案...',
  EMPTY: '没有题目',
  PREV_PAGE: '上一页',
  NEXT_PAGE: '下一页',
} as const

/** 评估页高频文案 */
export const EVAL = {
  TITLE: '评估报告',
  LAST_RUN: (ts: string) => `最近运行: ${ts}`,
  RAGAS_TITLE: 'RAGAS 指标',
  COMPARISON_TITLE: '检索策略对比',
  EMPTY: '暂无评估数据',
  LOAD_ERROR: '无法加载评估数据',
  TOTAL_QUESTIONS: '总题数',
  ERROR_COUNT: '错误数',
  HISTORY_TITLE: '历史快照',
  LOAD_DETAIL: '加载详情...',
  LOAD_DETAIL_FAILED: '加载失败',
} as const

/** 知识库管理高频文案 */
export const KB = {
  TITLE: '知识库管理',
  TOTAL: (n: number) => `共 ${n} 题`,
  SEARCH_PLACEHOLDER: '搜索题面或答案...',
  EMPTY: '没有题目',
  IMPORT: '导入',
} as const
