FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码和模板
COPY . .

# 创建数据目录
RUN mkdir -p /app/config /app/secrets

# 非 root 用户运行
RUN groupadd -r mcpuser && useradd -r -g mcpuser -d /app mcpuser
RUN chown -R mcpuser:mcpuser /app
USER mcpuser

EXPOSE 8900

CMD ["python", "main.py"]
