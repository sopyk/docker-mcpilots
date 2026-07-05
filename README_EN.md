![Docker-MCPilotS Banner](assets/banner.jpg)

# 🐳 Docker-MCPilotS

> 🌐 English | [简体中文](README.md)

Give AI Agents hands to manage Docker (MCP Server) — works great with containers on Synology NAS, and runs on any machine with Docker installed.

## 📦 Supported Architectures

| Architecture | Status | Applicable Devices |
|------|------|----------|
| **linux/amd64 (x86_64)** | ✅ Supported | Synology/QNAP and other Intel/AMD NAS, most VPS, standard PC servers |
| **linux/arm64** | 🚧 Planned | Raspberry Pi, Mac M-series, some ARM-based NAS |
| **linux/arm/v7** | ❌ Not Supported | Older Raspberry Pi and other 32-bit ARM devices |

> 💡 The current release only provides amd64 images. For ARM devices, please build the image from source.

## 🤔 Why This Project?

I use a Synology NAS daily, with dozens of Docker containers running on it: PT downloaders, media services, photo backups, code repos... Problems come up all the time — during deployments, upgrades, even during normal operation: containers won't start, permissions get messed up, networks stop working, resource usage spikes...

In the past, troubleshooting meant SSH'ing in and running commands. But NAS systems like Synology differ significantly from standard Linux servers — commands, paths, and permission systems are all customized. One wrong command could fail the operation at best, or brick the entire NAS at worst. Even worse, the NAS often runs critical services like photo backups and file sync — breaking it doesn't just take down a few containers, it takes down your whole home.

Or you could open Synology's clunky Docker UI and click around forever to find what you need.

Now that AI Agents have become so capable, I thought: **why not let AI help me manage these containers?** Let it troubleshoot issues, check logs, start/stop services — so I don't have to hold my breath every time something goes wrong.

But I couldn't just hand SSH access over to an Agent. NAS systems are too special, and the cost of a mistake is too high.

That's where MCP (Model Context Protocol) comes in — expose Docker management capabilities through the MCP interface, so the Agent can only perform operations we allow, with no risk to the system. It's essentially a **sandboxed Docker management tool**.

Once I had the idea, I just went for it. This project was built through **Vibe Coding**.

## ✨ Features Overview

### ✅ What It Can Do

| Category | What It Does |
|------|----------|
| 📦 Container Management | List, inspect, start, stop, restart, delete |
| 📜 Container Logs | View logs with time-based filtering (last 1 hour, last 30 minutes...) |
| 📊 Container Resources | Real-time CPU, memory, network usage |
| 🔍 Container Diagnostics | Process list, health status, network connections, mounted volumes, filesystem changes, image info |
| 🌐 Network Topology | View all Docker networks and the containers connected to them |
| 💾 Volume Inventory | View all volumes and their mount points |
| 🖥️ System Diagnostics | Host CPU, memory, disk, network info |
| 🔐 Access Control | Three roles: admin, operator, observer; permissions can be set per container |

### ❌ What It Cannot Do

| Limitation | Reason |
|------|------|
| 🚫 **Compose project management** (`docker compose up/down`) | Docker SDK does not support Compose operations; only individual containers can be managed |
| 🚫 **Edit Compose files** | The container cannot access compose files on the host |
| 🚫 **Build images** | `docker build` capability is not exposed for security reasons |
| 🚫 **Execute arbitrary commands** | `docker exec` is not provided to avoid command injection risks |
| 🚫 **Modify Docker network configuration** | Read-only view; cannot create/delete/modify networks |

## 📖 Usage

### 📋 Prerequisites

1. Deploy this MCP Server on your NAS (see deployment methods below)
2. Add the MCP Server in your AI client (OpenClaw, Hermes, Trae, Cursor, Claude Code, Codex...) with the address and API Key
3. Start chatting, let the Agent manage your containers

### 💬 Typical Scenarios

**Troubleshoot why a container won't start:**
> "Help me check what's going on with the jellyfin container? Why didn't it come up?"

The Agent will automatically call `inspect_container` to view details and `get_container_logs` to check error logs, then tell you the cause.

**Check container resource usage:**
> "Show me CPU and memory usage for all containers"

**Start/stop containers:**
> "Stop jellyfin, I need to upgrade it"

**View logs:**
> "Show me jellyfin logs from the last 30 minutes"

**Diagnose network issues:**
> "Help me check the network configuration of the jellyfin container, what are the port mappings?"

## 🚀 Deployment

### 🟢 Option 1: Pre-built Image (Recommended, NAS / Generic Linux)

Suitable for Synology/QNAP NAS, regular Linux servers — works out of the box.

**Steps:**

1. Create the project directory:
   ```bash
   mkdir docker-mcpilots && cd docker-mcpilots
   mkdir config secrets
   ```

2. Download and modify the config templates:
   - Copy from `templates/settings.yaml` to `config/settings.yaml`
   - Copy from `templates/auth.yaml` to `secrets/auth.yaml`
   - Remember to change the API Key!

3. Place `docker/docker-compose.yml` in the current directory

4. Modify `PUID`/`PGID` to your user ID (Synology users are typically 1026/100; on other systems, check with the `id` command)

5. Start it:
   ```bash
   docker compose up -d
   ```

**Config file overview:**

| File | Purpose |
|------|------|
| `config/settings.yaml` | Service port, Docker socket path, feature toggles |
| `secrets/auth.yaml` | API Key, role permissions, container scope (sensitive file) |

### 🟡 Option 2: Build from Source (Developers / ARM Devices)

Suitable for local development, or ARM devices (no ARM pre-built image is currently provided).

```bash
git clone https://github.com/sopyk/docker-mcpilots.git
cd docker-mcpilots
docker compose -f docker/docker-compose-build.yml up -d --build
```

Default port is 8900; remember to change the API Key in `secrets/auth.yaml`.

### 🔵 Option 3: VPS Host Installation

For scenarios that demand the lowest resource footprint, without nested Docker. See [docs/deploy-vps.md](docs/deploy-vps.md) for details.

## ⚙️ Configuration

### 🔑 API Key and Permissions

`secrets/auth.yaml` example:

```yaml
keys:
  - key: "your-secret-api-key"
    role: admin  # admin / operator / observer
```

- **admin**: Full permissions for all operations
- **operator**: Start, stop, restart containers; view logs and status (no deletion)
- **observer**: Read-only, can view but not operate

### 🎯 Container Scope Control

You can restrict an API Key to specific containers only:

```yaml
keys:
  - key: "download-containers-only"
    role: operator
    scope:
      include: ["qbittorrent", "aria2*", "transmission"]
      exclude: ["*"]
```

## 📁 File Structure

```
docker-mcpilots/
├── main.py                    # Entry point
├── core/                      # Core modules
│   ├── config.py             # Config loading
│   ├── auth.py               # Permission checks
│   ├── docker_client.py      # Docker SDK wrapper
│   └── system_diag.py        # System diagnostics
├── tools/                    # MCP tools
│   ├── container_tools.py    # Container management
│   ├── image_tools.py        # Image management
│   ├── docker_diag_tools.py # Network/volume diagnostics
│   └── diag_tools.py        # System diagnostics
├── templates/                 # Config templates
│   ├── settings.yaml
│   └── auth.yaml
├── docker/                   # Docker related
│   ├── Dockerfile
│   ├── entrypoint.sh        # Entry script
│   ├── docker-compose.yml    # Pre-built image version (recommended)
│   └── docker-compose-build.yml  # Build-from-source version
└── tests/                    # Test cases (for development, can be ignored for deployment)
```

## 🛠️ Tech Stack

- Python 3.11 + FastMCP 3.x
- docker Python SDK 7.x
- psutil 7.x
- Single-container architecture, minimal resource footprint (~50MB RAM)

## 🧪 Testing

```bash
# Unit tests
pytest tests/

# End-to-end tests
docker run -d --name dm-e2e-test alpine sh -c 'while true; do echo heartbeat; sleep 5; done'
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets python main.py &
python scripts/e2e_test.py
docker rm -f dm-e2e-test
```

## 🗺️ Roadmap

- 🖼️ **Web UI**: A graphical management interface so you can intuitively view and manage containers without AI (for scenarios where you don't want to use an Agent, or for quick browsing)
- 🍓 **ARM architecture support**: Provide arm64 pre-built images, covering Raspberry Pi, Mac M-series, and similar devices
- 📈 **More diagnostic capabilities**: Container event streams, resource usage history charts, anomaly alerts
- 🔗 **Multi-node management**: One MCP Server managing Docker across multiple machines

## ⚠️ Risk Disclaimer

**By using this project, you acknowledge and accept the following risks:**

1. **Container operations carry risk**: Stopping, deleting, and similar operations may cause data loss or service interruption. Make sure you understand the consequences before acting
2. **Configure permissions carefully**: The admin role has full permissions — keep your API Key safe
3. **Internal network only**: The default config listens only on the loopback address; do not expose it directly to the public internet
4. **Use at your own risk**: This project is open source. Users must assess risks themselves; the author is not responsible for any losses incurred during use
5. **Backups recommended**: Back up important data and configs, and confirm before performing operations

**🔒 Security recommendations:**
- Always change the default API Key in production
- Restrict container scope permissions to only what's necessary
- Access through a reverse proxy with TLS (see the VPS deployment docs)
- Check logs regularly and investigate anomalies promptly

## 📄 License

MIT License - see the [LICENSE](LICENSE) file.

## 🔗 Links

- 🐙 GitHub: https://github.com/sopyk/docker-mcpilots
- 🐛 Issues: https://github.com/sopyk/docker-mcpilots/issues
- 📦 Image registries:
  - GHCR: `ghcr.io/sopyk/docker-mcpilots`
  - Docker Hub: `sopyk/docker-mcpilots`
