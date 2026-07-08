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
| `MCP_CONFIG_DIR` | Config file directory | `/app/config` |
| `MCP_SECRETS_DIR` | Sensitive file directory | `/app/secrets` |

## Option 2: Build from Source (Developers / ARM Devices)

Suitable for local development debugging, or ARM architecture devices (ARM pre-built images are not currently available).

```bash
git clone https://github.com/sopyk/docker-mcpilots.git
cd docker-mcpilots
docker compose -f docker/docker-compose-build.yml up -d --build
```

Default port is 8900, remember to change the API Key in `secrets/auth.yaml`.

## Option 3: Direct Installation on VPS Host

Suitable for scenarios seeking minimal resource usage, no Docker-in-Docker. See [VPS Deployment](deploy-vps.md).

## Supported Architectures

| Architecture | Status | Supported Devices |
|--------------|--------|-------------------|
| **linux/amd64 (x86_64)** | ✅ Supported | Synology/QNAP Intel/AMD NAS, most VPS, regular PC servers |
| **linux/arm64** | 🚧 Planned | Raspberry Pi, Mac M-series, some ARM NAS |
| **linux/arm/v7** | ❌ Not supported | Older Raspberry Pi and other 32-bit ARM devices |

> 💡 Currently only amd64 images are provided. ARM users please build from source.
