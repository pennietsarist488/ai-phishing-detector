# AI钓鱼网站检测后端 - Docker镜像
# 基于官方Python镜像构建

FROM python:3.10-slim

LABEL maintainer="AI钓鱼检测团队"
LABEL description="AI钓鱼网站动态识别及防护系统 - 后端服务"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装Playwright浏览器（用于表单分析的页面内容提取）
RUN playwright install chromium --with-deps

# 复制项目代码
COPY backend/ ./backend/
COPY models/ ./models/

# 创建非root用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# 启动命令
CMD ["python", "-m", "backend.app"]