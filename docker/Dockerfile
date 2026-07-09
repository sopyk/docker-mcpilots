FROM python:3.11-alpine

WORKDIR /app

# 安装 Python 依赖（把临时构建工具放在同一个 RUN 命令里！安装后立即删除！）
COPY requirements.txt .
RUN apk add --no-cache su-exec build-base libffi-dev openssl-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    # 安装完依赖后立即删除构建工具！减小镜像体积！
    apk del build-base libffi-dev openssl-dev && \
    rm -rf /var/cache/apk/*

# 复制源代码（精确复制，避免把 .venv/tests/docs/scripts 等无关文件打入镜像）
COPY core/ ./core/
COPY tools/ ./tools/
COPY web/ ./web/
COPY main.py .
COPY templates/ ./templates/

# 复制 entrypoint（从 docker/ 子目录取出放到容器 /app/ 根）
COPY docker/entrypoint.sh /app/entrypoint.sh

# 创建数据目录（先以 root 创建，entrypoint 会调整权限）
RUN mkdir -p /app/config /app/secrets

# 创建 mcpuser 用户（默认 UID/GID 会在 entrypoint 中按需调整）
RUN addgroup -S mcpuser && adduser -S mcpuser -G mcpuser -h /app

# entrypoint 需要可执行权限
RUN chmod +x /app/entrypoint.sh

EXPOSE 8900

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "main.py"]
