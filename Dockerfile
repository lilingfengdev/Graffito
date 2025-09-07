# OQQWall Docker镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    chromium \
    chromium-driver \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p data data/cache data/logs data/cookies

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium

# 暴露端口（NoneBot FastAPI driver）
EXPOSE 8082

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8082/health')" || exit 1

# 启动命令（NoneBot 入口）
CMD ["python", "bot.py"]
