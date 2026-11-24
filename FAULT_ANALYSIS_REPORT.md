# Fault Analysis Report: docker-mcpilots Service Freeze (Issue #8900)

**Date**: 2026-11-24
**Image**: `ghcr.io/sopyk/docker-mcpilots:v2.1.4`
**Status**: Recovered via docker restart; optimizations not yet implemented

---

## 1. Fault Conclusion (One-sentence)

**Container "Up" but service frozen: The event loop is blocked by a synchronous blocking call, causing the HTTP port to accept handshakes but not respond.** This is not a network issue or crash — it is a code design defect triggered by a stuck exec script.

---

## 2. Evidence Chain

| Layer | Observation | Conclusion |
|-------|-------------|------------|
| **Port** | `nc` passes, TCP handshake succeeds; local curl times out after 12s (NAS 5s, zero bytes) | Someone accepted, no one responded |
| **Kernel** | Port 8900 `LISTEN Recv-Q=129`; many `CLOSE_WAIT` with unread rx_queue | Connections queuing, application not reading |
| **Process** | PID 1 `python main.py` sleeping, CPU 0%, Threads=1 | Event loop blocked, not busy-wait/crash |
| **Trigger** | Root `python3` (PID846) stuck in `recv()`: base64 script directly connecting docker.sock, `while True: recv()` waiting for EOF. Docker HTTP keep-alive does not close the connection. | Process permanently stuck |
| **Config** | `Healthcheck: null`, RestartCount=0 | Monitoring blind spot, Docker cannot auto-rescue |

---

## 3. Root Cause (Code-Level)

### 3.1 Direct Trigger: Deadlocked exec Subprocess
Someone (an agent or admin) used the exec tool to run a script in the container:

```python
s = socket.socket(AF_UNIX, SOCK_STREAM)
s.connect('/var/run/docker.sock')
s.sendall(b'GET /images/json?all=1 HTTP/1.1\r\nHost: docker\r\n\r\n')
while True:
    d = s.recv(65536)   # ← Docker response is keep-alive, never closes → infinite wait
    if not d: break
    buf += d
```
→ That process: root, sleeping, CPU 0%, permanently stuck.

### 3.2 Fundamental Defect: Synchronous Call in async Function
**File**: `/app/tools/exec_tools.py` L47

```python
# Current (blocking)
return docker_client.exec_container(container_id, command, workdir=workdir)
```

**File**: `/app/core/docker_client.py` L527 — `exec_container()` is a **synchronous** Docker SDK call.

**Impact**: The server runs **single worker, single event loop** (uvicorn). Any synchronous blocking call freezes the entire event loop, bringing all routes to a standstill.

> **Same-risk files**: All `async def` tools in `container_tools.py`, `image_tools.py`, `diag_tools.py`, `docker_diag_tools.py`, `settings_tools.py`, `user_mgmt_tools.py` that directly call synchronous methods in `core/docker_client.py` are **one and the same risk**.

### 3.3 Amplifying Defect: No Healthcheck, No Auto-Recovery
- `docker inspect` → `"Healthcheck": null`
- `restart: unless-stopped` only works on process exit; freeze-without-exit → no restart
- Without healthcheck, monitoring cannot detect the freeze; without auto-restart, manual intervention required.

---

## 4. Actions Taken (Already Done)

- `docker restart docker-mcpilots` — service recovered.
- Verified: `/health` → 200, `/` → 303, `/mcp` → 400 (GET not accepted, normal).
- The stuck root script was cleared with the restart.

> **Note**: All P0–P2 items below are **suggestions not yet implemented**. They require code changes and/or image rebuild.

---

## 5. Optimization Checklist (Priority Order)

### P0 — Eliminate Event Loop Blocking (Code Change, Rebuild Image)

**File**: `/app/tools/exec_tools.py` L47

**Change**: Wrap the synchronous call with `asyncio.to_thread()` so it runs in a thread pool and does not block the event loop.

```python
# Before (blocking)
return docker_client.exec_container(container_id, command, workdir=workdir)

# After (non-blocking)
import asyncio
return await asyncio.to_thread(
    docker_client.exec_container, container_id, command, workdir=workdir
)
```

**Same fix needed for** (all async tools calling sync docker_client methods):
- `container_tools.py`
- `image_tools.py`
- `diag_tools.py`
- `docker_diag_tools.py`
- `settings_tools.py`
- `user_mgmt_tools.py`

**Benefit**: A single slow exec call will no longer freeze the entire service.

---

### P1 — Hard Timeout + Watchdog for Exec

- **docker_client.exec_container** internal `exec_run` should set a `timeout` (Docker SDK supports it). If timeout exceeds, return error instead of permanent hang.
- For exec-spawned subprocesses: add timeout + kill mechanism; avoid `while True: recv()`-type scripts that block threads.
- **Upstream fix**: The base64 script mentioned should parse HTTP response via `Content-Length` or chunked encoding instead of `while True: recv()` waiting for EOF.

---

### P2 — Add Observability: Healthcheck

**NAS compose file**: `/volume3/docker/compose-docker-mcpilots/compose.yaml` (add under `docker-mcpilots` service)

```yaml
healthcheck:
  test: ["CMD", "wget", "-qO-", "http://127.0.0.1:8900/health"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 15s
```

- Confirm `wget` is available in the container; if not, use `python3 -c "..."` to hit `/health`.
- With healthcheck configured, Watchtower or custom scripts can auto-restart on `unhealthy`, or at least the issue will be visible in Portainer/alerting.

---

### P3 — Security Review

- Port 8900 is listed as a high-exposure face (alongside 9000 Portainer, 2222 webssh2).
- **Suggestion**: Bind to intranet/Tailnet, add access control. Confirm whether `0.0.0.0` full-network listen is really needed.
- Ensure exec tools remain scope-restricted (already have `exec_enabled` gate + `exec:run` permission).

---

## 6. This Session Summary

- **Only action taken**: `docker restart docker-mcpilots` to recover service.
- **All P0–P2 items are unimplemented suggestions** — improving code, adding timeouts, and adding healthcheck require code changes and/or image rebuild, independent of this incident.
- **Root cause confirmed**: Synchronous blocking call in async event loop + a stuck exec script = service freeze.