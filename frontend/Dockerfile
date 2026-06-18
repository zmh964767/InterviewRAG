# Stage 1: deps — 单独装依赖,利用 Docker 缓存
FROM node:20-alpine AS deps
WORKDIR /app
# 淘宝 npm 镜像（国内加速）
RUN npm config set registry https://registry.npmmirror.com
COPY package.json package-lock.json* ./
RUN npm ci

# Stage 2: build — 跑 next build,产出 .next/standalone
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# 当前前端走相对路径 + Next.js rewrites 代理到后端 8080，无需 NEXT_PUBLIC_API_URL。
# 保留 ARG 作为文档：将来前后端分离部署时，取消下方注释并恢复
# frontend/lib/api.ts 和 contexts/AdminAuthContext.tsx 的 API_BASE。
# ARG NEXT_PUBLIC_API_URL=http://localhost:8080
# ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Stage 3: runner — 最终镜像,只装 standalone + static
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000 \
    HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
