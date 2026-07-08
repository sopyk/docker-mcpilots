# Toolbox Container

## Why Use a Toolbox Container?

If you want to use the `exec_container` tool to run commands inside containers, **we strongly recommend using a dedicated toolbox container** instead of executing commands directly in your production containers.

- 🛡️ **Safe isolation**: exec operations only happen inside the toolbox, never touching your business containers
- 🧪 **Worry-free testing**: The toolbox is built for troubleshooting — experiment freely without risk
- 🔧 **Built-in tools**: Pre-installed with various diagnostic tools (docker CLI, curl, dig, nc, etc.)
- 📁 **Mount for inspection**: Mount Docker socket and common directories to inspect the host Docker environment and files from inside the container

## What Can the Toolbox Container Do?

- Use `docker` commands to check status, logs, and config of all containers on the host
- Use `curl` / `wget` to test network connectivity between containers
- Use `ping` / `traceroute` to diagnose network issues
- Inspect mounted directories to check file permissions and configurations
- Install temporary tools for deep troubleshooting

## Usage Steps

1. Start the toolbox container (config file at `docker/docker-compose-toolbox.yml`):
   ```bash
   docker compose -f docker-compose-toolbox.yml up -d
   ```

   > 💡 First start automatically installs common diagnostic tools, takes about 30 seconds to 1 minute.

2. Enable "Container Exec" feature in Docker-MCPilotS Web UI settings

3. Configure scope restrictions for API Keys that need exec access, **only allowing exec on the `mcp-toolbox` container**:
   ```yaml
   # scope config for the corresponding key in secrets/auth.yaml
   scope:
     exec:
       include:
         - mcp-toolbox
   ```

4. Then let the Agent troubleshoot inside the toolbox via `exec_container`, for example:
   > "Use the toolbox container to check the status of all containers"
   > "Use curl to test if port 80 on the nginx container is reachable"

## About the Build Approach

The toolbox container uses **auto-install tools on startup** (Option A), advantages:

- Universal: Works on any machine, no pre-built image required
- Flexible: Add any tools by modifying the apk add list in command
- Simple: One compose file, no extra Dockerfile needed

Disadvantage: First startup takes tens of seconds to install tools. Subsequent restarts are fast (as long as the container isn't deleted, tools persist).

## Mount Notes

The toolbox container mounts the Docker socket (read-only) by default, so you can use `docker` commands inside the container to manage the host's Docker environment.

Remove this mount if you don't need docker command access.

Optionally mount common NAS directories (read-only) for easier file troubleshooting:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
  - /volume1/docker:/data/docker:ro
  - /volume1/homes:/data/homes:ro
```

## Resource Limits

Default limits: 256MB memory, 0.5 CPU cores — sufficient for troubleshooting. Adjust as needed.
