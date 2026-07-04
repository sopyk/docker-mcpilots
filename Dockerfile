FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（gosu 用于降权运行）
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码和模板
COPY . .

# 创建数据目录（先以 root 创建，entrypoint 会调整权限）
RUN mkdir -p /app/config /app/secrets

# 创建 mcpuser 用户（默认 UID/GID 会在 entrypoint 中按需调整）
RUN groupadd -r mcpuser && useradd -r -g mcpuser -d /app mcpuser

# entrypoint 需要可执行权限
RUN chmod +x /app/entrypoint.sh

EXPOSE 8900

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "main.py"]
