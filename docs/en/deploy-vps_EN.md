> 🌐 English | [简体中文](deploy-vps.md)

# VPS Host-Native Deployment

Use case: a clean Linux VPS where you want to avoid container nesting and keep resource usage minimal.

## Prerequisites

- Linux server (Ubuntu/Debian/CentOS all work)
- Docker daemon installed and running
- Python 3.11+
- The runtime user can access `/var/run/docker.sock`

## 1. Install Docker (if not installed)

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
```

## 2. Grant the runtime user access to docker.sock

```bash
sudo usermod -aG docker $USER
newgrp docker
```

## 3. Get the project code

```bash
# Option 1: Clone from GitHub
git clone https://github.com/sopyk/docker-mcpilots.git
cd docker-mcpilots

# Option 2: Download the slim package from Release
# wget https://github.com/sopyk/docker-mcpilots/releases/download/v1.0.0/docker-mcpilots-v1.0.0.tar.gz
# tar -xzf docker-mcpilots-v1.0.0.tar.gz
# cd docker-mcpilots
```

## 4. Install Python dependencies (UV recommended)

**Option 1: UV (recommended, 10–100x faster)**

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment and install dependencies
uv venv .venv
uv pip install -r requirements.txt
```

**Option 2: Traditional pip**

```bash
sudo apt install -y python3.11 python3.11-venv
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 5. Prepare the configuration

```bash
mkdir -p config secrets
cp templates/settings.yaml config/
cp templates/auth.yaml secrets/
chmod 600 secrets/auth.yaml
# Edit secrets/auth.yaml to replace the default API Key with your own
vi secrets/auth.yaml
```

## 6. Start

### Manual start (for testing)

```bash
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets .venv/bin/python main.py
```

### systemd management (for production)

Create `/etc/systemd/system/docker-mcpilots.service`:

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

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now docker-mcpilots
sudo systemctl status docker-mcpilots
```

## 7. Production hardening (strongly recommended)

By default the service listens on `0.0.0.0:8900`, which is risky to expose directly to the public internet. Recommended:

### 7.1 Listen only on localhost

Edit `config/settings.yaml`:

```yaml
server:
  host: "127.0.0.1"
  port: 8900
```

### 7.2 nginx reverse proxy + TLS

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
        proxy_buffering off;          # Required for MCP streaming responses
        proxy_read_timeout 86400s;    # Long-lived connection
    }
}
```

### 6.3 Firewall

```bash
sudo ufw allow 443/tcp
sudo ufw deny 8900/tcp
sudo ufw enable
```

## 7. Verify

```bash
curl http://127.0.0.1:8900/health
# Expected: {"status":"ok","version":"1.0.0"}

# Call an MCP tool (requires API Key)
curl -X POST http://127.0.0.1:8900/mcp \
  -H "Authorization: Bearer sk-dm-your-key" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

## Upgrade

```bash
cd /opt/docker-mcpilots
git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart docker-mcpilots
```

## Troubleshooting

| Symptom | Troubleshooting |
|---|---|
| Startup reports `Permission denied: /var/run/docker.sock` | The runtime user is not in the docker group; run `sudo usermod -aG docker $USER && newgrp docker` |
| Tool call returns 401 | API Key mismatch; check `secrets/auth.yaml` |
| Tool call returns `container not found` | Verify the container name; use `docker ps` to inspect |
| systemd fails to start | Check logs with `journalctl -u docker-mcpilots -f` |
