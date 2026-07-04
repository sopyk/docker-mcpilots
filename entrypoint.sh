#!/bin/bash
set -e

# ── PUID/PGID 支持 ──
# 用法：在 docker-compose 中设置 environment:
#   - PUID=1026
#   - PGID=100
# 即可让容器以群晖用户的身份读写挂载卷

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# 检查当前用户是否已经是目标 UID/GID
CURRENT_UID=$(id -u mcpuser 2>/dev/null || echo "")
CURRENT_GID=$(id -g mcpuser 2>/dev/null || echo "")

if [ "${CURRENT_UID}" != "${PUID}" ] || [ "${CURRENT_GID}" != "${PGID}" ]; then
    echo "[entrypoint] Adjusting mcpuser to UID=${PUID}, GID=${PGID}"

    # 如果目标 GID 已存在但不是 mcpuser 的组，创建新组
    if getent group "${PGID}" >/dev/null 2>&1; then
        GROUP_NAME=$(getent group "${PGID}" | cut -d: -f1)
        echo "[entrypoint] GID ${PGID} already exists as group '${GROUP_NAME}'"
    else
        groupmod -g "${PGID}" mcpuser 2>/dev/null || true
    fi

    # 修改 mcpuser 的 UID 和 GID
    usermod -u "${PUID}" -g "${PGID}" mcpuser 2>/dev/null || true

    # 修正 /app 下文件属主（避免旧 UID 的残留文件）
    chown -R mcpuser:"${PGID}" /app/templates /app/core /app/tools /app/*.py 2>/dev/null || true
fi

# 确保挂载目录对 mcpuser 可写
# 注意：如果挂载卷在宿主机上不存在，Docker 会以 root 创建它
# 这里用 root 权限修正，让 mcpuser 能正常读写
chown -R "${PUID}:${PGID}" /app/config /app/secrets 2>/dev/null || true
chmod 755 /app/config /app/secrets 2>/dev/null || true

# 修正 docker.sock 的组权限，让 mcpuser 的主组可以访问
# gosu 会清除补充组，所以 group_add 方案无效
# 直接将 socket 组改为 mcpuser 的主组是最可靠的方案
if [ -S /var/run/docker.sock ]; then
    chgrp "${PGID}" /var/run/docker.sock 2>/dev/null || true
    echo "[entrypoint] Set docker.sock group to GID=${PGID}"
fi

echo "[entrypoint] Running as mcpuser (UID=${PUID}, GID=${PGID})"

# 降权运行主程序
exec gosu mcpuser "$@"
