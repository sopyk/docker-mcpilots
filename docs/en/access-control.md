# Access Control

## Role Description

| Role | Permissions |
|------|-------------|
| **admin** | Full access, including container deletion and exec commands |
| **operator** | Start, stop, restart containers, view logs and status (cannot delete, cannot exec) |
| **observer** | Read-only, can only view, cannot perform operations |

## Configuration

Edit `secrets/auth.yaml`:

```yaml
keys:
  - key: "your-secret-api-key"
    role: admin
```

## Container Scope Control (Scope)

You can restrict an API Key to only operate on specific containers:

```yaml
keys:
  - key: "download-only key"
    role: operator
    scope:
      include: ["qbittorrent", "aria2*", "transmission"]
      exclude: ["*"]
```

- `include`: List of allowed containers, supports wildcard `*`
- `exclude`: List of forbidden containers, supports wildcard `*`
- Without scope configuration, all containers are accessible

## exec Permission Notes

The `exec_container` tool is **disabled** by default and must be manually enabled in settings.

When enabled, only the **admin role** can use it. We recommend using scope restrictions to only allow exec on specific toolbox containers. See [Toolbox Container](toolbox-container.md).

## Security Recommendations

- Always change the default API Key in production
- Assign roles based on actual needs, don't give admin to everyone
- Restrict container scope permissions, only give what's necessary
- Access via reverse proxy with TLS
- Regularly check logs, investigate anomalies promptly
