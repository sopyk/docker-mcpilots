> 🌐 [English](deploy-vps_EN.md) | 简体中文

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

## 3. 获取项目代码

```bash
# 方式一：从 GitHub 克隆
git clone https://github.com/sopyk/docker-mcpilots.git
cd docker-mcpilots

# 方式二：从 Release 下载精简包
# wget https://github.com/sopyk/docker-mcpilots/releases/download/v1.0.0/docker-mcpilots-v1.0.0.tar.gz
# tar -xzf docker-mcpilots-v1.0.0.tar.gz
# cd docker-mcpilots
```

## 4. 安装 Python 依赖（推荐用 UV）

**方式一：UV（推荐，速度快 10-100 倍）**

```bash
# 安装 UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv venv .venv
uv pip install -r requirements.txt
```

**方式二：传统 pip**

```bash
sudo apt install -y python3.11 python3.11-venv
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 5. 准备配置

```bash
mkdir -p config secrets
cp templates/settings.yaml config/
cp templates/auth.yaml secrets/
chmod 600 secrets/auth.yaml
# 编辑 secrets/auth.yaml，把默认 API Key 改成你自己的
vi secrets/auth.yaml
```

## 6. 启动

### 手动启动（测试用）

```bash
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets .venv/bin/python main.py
```

### systemd 托管（生产用）

创建 `/etc/systemd/system/docker-mcpilots.service`：

```ini
[Unit]
Description=Docker-MCPilotS MCP Server
After=docker.service network.target
Requires=docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/docker-mcpilots
Environment=MCP_CONFIG_DIR=/opt/docker-mcpilots/config
Environment=MCP_SECRETS_DIR=/opt/docker-mcpilots/secrets
Environment=TZ=Asia/Shanghai
ExecStart=/opt/docker-mcpilots/.venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now docker-mcpilots
sudo systemctl status docker-mcpilots
```

## 7. 生产环境加固（强烈建议）

默认监听 `0.0.0.0:8900`，公网直接暴露有风险。推荐：

### 7.1 改为只监听本地

编辑 `config/settings.yaml`：

```yaml
server:
  host: "127.0.0.1"
  port: 8900
```

### 7.2 nginx 反代 + TLS

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
# 期望: {"status":"ok","version":"1.0.0"}

# 调用 MCP 工具（需带 API Key）
curl -X POST http://127.0.0.1:8900/mcp \
  -H "Authorization: Bearer sk-dm-your-key" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

## 升级

```bash
cd /opt/docker-mcpilots
git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart docker-mcpilots
```

## 故障排查

| 现象 | 排查 |
|---|---|
| 启动报 `Permission denied: /var/run/docker.sock` | 运行用户没在 docker 组，`sudo usermod -aG docker $USER && newgrp docker` |
| 工具调用返回 401 | API Key 不匹配，检查 `secrets/auth.yaml` |
| 工具调用返回 `container not found` | 检查容器名是否正确，`docker ps` 查看 |
| systemd 启动失败 | `journalctl -u docker-mcpilots -f` 查看日志 |
