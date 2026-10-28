# Deployment Guide

## Option 1: Pre-built Image (Recommended, NAS / Generic Linux)

Suitable for Synology/QNAP NAS, regular Linux servers — works out of the box.

**Steps:**

1. Create the project directory:
   ```bash
   mkdir docker-mcpilots && cd docker-mcpilots
   mkdir config secrets
   ```

2. Place `docker/docker-compose.yml` in the current directory

3. Modify environment variables in `docker-compose.yml`:
   - Change `ADMIN_PASSWORD` to your desired admin password
   - Change `PUID`/`PGID` to your user ID (Synology users are typically 1026/100; on other systems, check with the `id` command)
   - Optional: Set `INITIAL_API_KEYS` for initial API Keys (format: name1:key1:role1,name2:key2:role2)
   - Optional: Set `ADMIN_USERNAME` to change the default admin username

4. Start it:
   ```bash
   docker compose up -d
   ```

**Config file overview:**

| File | Purpose |
|------|------|
| `config/settings.yaml` | Service port, Docker socket path, feature toggles |
| `secrets/auth.yaml` | API Keys, role permissions, container scopes (sensitive) |
| `secrets/admin.yaml` | Web UI admin credentials (sensitive) |

**Environment variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `TZ` | Timezone | `Asia/Shanghai` |
| `PUID` | UID of the user running the container | `1000` |
| `PGID` | GID of the user running the container | `1000` |
| `ADMIN_USERNAME` | Web UI admin username | `admin` |
| `ADMIN_PASSWORD` | Web UI admin password (set on first start) | Randomly generated with warning |
| `INITIAL_API_KEYS` | Initial API Key list, format: `name1:key1:role1,name2:key2:role2` | None |
| `MCP_SESSION_IDLE_TIMEOUT` | MCP HTTP session idle timeout. `none` = never expire (same as 2.1.2); a number (e.g. `86400`) reclaims orphaned sessions | `none` |
| `MCP_CONFIG_DIR` | Config file directory | `/app/config` |
| `MCP_SECRETS_DIR` | Sensitive file directory | `/app/secrets` |

### MCP session lifecycle (v2.1.3-rc.5+)

MCP Streamable HTTP sessions live **in server memory**. The rules:

- **Default `MCP_SESSION_IDLE_TIMEOUT=none`**: no idle reaping. A session is destroyed only when the client disconnects (`DELETE`) or the server process exits (container/service restart).
- **Set to a number of seconds** (e.g. `86400`): only sessions with **no request in flight and no open GET/SSE stream** are reaped; each reaped session logs `Session <id> idle timeout` at INFO. Useful for long-running deployments where many clients reconnect and leave orphaned sessions.
- **A restart invalidates every session**: the session table is in memory, so after a container restart a client still sending its old `mcp-session-id` gets one `404 Session not found`, logged as `Rejected request with unknown or expired session ID: <id>`. The client re-`initialize`s and recovers — expected behaviour, not a fault.
- **Concurrent session cap**: the SDK allows 10000 sessions by default; beyond that new sessions are refused with WARNING `Refusing to open a new session: N sessions are already open`. Normal usage never hits this; if it does, clients are leaking sessions — configure an idle timeout.
- **Confirm the setting took effect**: the startup log contains
  `core.mcp_session: MCP HTTP 会话空闲超时：已关闭（会话永不过期）` (or `...：86400 秒`).

> Background: `fastmcp` 4.1.0 changed the default idle timeout to 1800s (4.0.x never expired), which caused `transport session expired` / empty tool lists in rc.4. rc.5 restores "never expire" by default and pins every dependency in `requirements.lock`.

## Option 2: Build from Source (Developers)

Suitable for local development debugging, or scenarios requiring custom modifications.

```bash
git clone https://github.com/sopyk/docker-mcpilots.git
cd docker-mcpilots
docker compose -f docker/docker-compose-build.yml up -d --build
```

Default port is 8900, remember to change the API Key in `secrets/auth.yaml`.

## Option 3: Direct Installation on VPS Host

Suitable for scenarios seeking minimal resource usage, no Docker-in-Docker. See [VPS Deployment](deploy-vps_EN.md).

## Supported Architectures

| Architecture | Status | Supported Devices |
|--------------|--------|-------------------|
| **linux/amd64 (x86_64)** | ✅ Supported | Synology/QNAP Intel/AMD NAS, most VPS, regular PC servers |
| **linux/arm64** | ✅ Supported | Raspberry Pi, Mac M-series, some ARM NAS |
| **linux/arm/v7** | ❌ Not supported | Older Raspberry Pi and other 32-bit ARM devices |

> 💡 Pre-built images are provided for both amd64 and arm64 architectures; docker pull automatically fetches the variant matching your CPU. For 32-bit ARM (arm/v7) devices, please build from source.
