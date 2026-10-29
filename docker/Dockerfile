# 基础镜像按 digest 固定（manifest list，含 linux/amd64 + linux/arm64）：
# 上游重新发布 python:3.11-alpine 标签不会影响构建结果；升级基础镜像时改这里的 digest 并跑全量测试。
# 第一阶段：Build 阶段
FROM python:3.11-alpine@sha256:79440cc1dfa86a5f98d67efcd219726a8e9d8083cc0aafd27c7bef5976c38868 AS builder
WORKDIR /app

# 安装构建工具，只在这阶段使用
RUN apk add --no-cache build-base libffi-dev openssl-dev

# 安装 Python 依赖（从 lock 安装，保证传递依赖版本不漂移）
COPY requirements.lock ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock && \
    # 清理 Python 的 pyc 缓存，减小体积
    find /install -type d -name __pycache__ -prune -exec rm -rf {} + && \
    find /install -type f -name "*.pyc" -delete && \
    find /install -type f -name "*.pyo" -delete

# 第二阶段：Final 阶段（只保留运行时所需）
FROM python:3.11-alpine@sha256:79440cc1dfa86a5f98d67efcd219726a8e9d8083cc0aafd27c7bef5976c38868

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
