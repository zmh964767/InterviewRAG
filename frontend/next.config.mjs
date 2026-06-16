/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker 部署：standalone 模式减小运行时镜像（见 .trellis/tasks/06-13-docker-deploy/design.md）
  output: 'standalone',

  // API 代理（开发环境）
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8080'
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
