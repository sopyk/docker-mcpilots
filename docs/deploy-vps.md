# VPS 宿主机直装部署

适用场景：干净的 Linux VPS，希望省去容器嵌套、资源占用最低。

## 前置条件

- Linux 服务器（Ubuntu/Debian/CentOS 均可）
- 已安装 Docker daemon 并运行
- Python 3.11+
- 运行用户能访问 `/var/run/docker.sock`

## 1. 安装 Docker（如未安装）

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
```

## 2. 让运行用户能访问 docker.sock

```bash
sudo usermod -aG docker $USER
newgrp docker
```

## 3. 安装 Python 依赖

```bash
sudo apt install -y python3.11 python3.11-venv
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 4. 准备配置

```bash
mkdir -p config secrets
cp templates/settings.yaml config/
cp templates/auth.yaml secrets/
chmod 600 secrets/auth.yaml
# 编辑 secrets/auth.yaml，把默认 API Key 改成你自己的
vi secrets/auth.yaml
```

## 5. 启动

### 手动启动（测试用）

```bash
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets .venv/bin/python main.py
```

### systemd 托管（生产用）

创建 `/etc/systemd/system/docker-mcp.service`：

```ini
[Unit]
Description=DockerMaintainer MCP Server
After=docker.service network.target
Requires=docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/dockermaintainer
Environment=MCP_CONFIG_DIR=/opt/dockermaintainer/config
Environment=MCP_SECRETS_DIR=/opt/dockermaintainer/secrets
Environment=TZ=Asia/Shanghai
ExecStart=/opt/dockermaintainer/.venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now docker-mcp
sudo systemctl status docker-mcp
```

## 6. 生产环境加固（强烈建议）

默认监听 `0.0.0.0:8900`，公网直接暴露有风险。推荐：

### 6.1 改为只监听本地

编辑 `config/settings.yaml`：

```yaml
server:
  host: "127.0.0.1"
  port: 8900
```

### 6.2 nginx 反代 + TLS

```nginx
server {
    listen 443 ssl;
    server_name mcp.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/mcp.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8900;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;          # MCP 流式响应需要关闭缓冲
        proxy_read_timeout 86400s;    # 长连接
    }
}
```

### 6.3 防火墙

```bash
sudo ufw allow 443/tcp
sudo ufw deny 8900/tcp
sudo ufw enable
```

## 7. 验证

```bash
curl http://127.0.0.1:8900/health
# 期望: {"status":"ok","version":"0.1.3"}

# 调用 MCP 工具（需带 API Key）
curl -X POST http://127.0.0.1:8900/mcp \
  -H "Authorization: Bearer sk-dm-your-key" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

## 升级

```bash
cd /opt/dockermaintainer
git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart docker-mcp
```

## 故障排查

| 现象 | 排查 |
|---|---|
| 启动报 `Permission denied: /var/run/docker.sock` | 运行用户没在 docker 组，`sudo usermod -aG docker $USER && newgrp docker` |
| 工具调用返回 401 | API Key 不匹配，检查 `secrets/auth.yaml` |
| 工具调用返回 `container not found` | 检查容器名是否正确，`docker ps` 查看 |
| systemd 启动失败 | `journalctl -u docker-mcp -f` 查看日志 |
