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
    RETRY: '重试',
    DISMISS: '关闭',
  },
} as const
