# 第一阶段：Build 阶段
FROM python:3.11-alpine AS builder
WORKDIR /app

# 安装构建工具，只在这阶段使用
RUN apk add --no-cache build-base libffi-dev openssl-dev

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    # 清理 Python 的 pyc 缓存，减小体积
    find /install -type d -name __pycache__ -prune -exec rm -rf {} + && \
    find /install -type f -name "*.pyc" -delete && \
    find /install -type f -name "*.pyo" -delete

# 第二阶段：Final 阶段（只保留运行时所需）
FROM python:3.11-alpine

WORKDIR /app

# 只安装运行时依赖（su-exec，不用 build-base！）
RUN apk add --no-cache su-exec

# 从 builder 阶段复制安装好的 Python 包
COPY --from=builder /install /usr/local

# 复制源代码
COPY core/ ./core/
COPY tools/ ./tools/
COPY web/ ./web/
COPY main.py .
COPY templates/ ./templates/
COPY docker/entrypoint.sh /app/entrypoint.sh

RUN mkdir -p /app/config /app/secrets
RUN addgroup -S mcpuser && adduser -S mcpuser -G mcpuser -h /app
RUN chmod +x /app/entrypoint.sh

EXPOSE 8900

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "main.py"]
