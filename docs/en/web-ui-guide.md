# Web UI Guide

After deployment, visit `http://<your-ip>:8900/ui/` to access the Web UI.

## Pages

- **Dashboard**: View CPU/memory usage, container/image counts, recent audit logs
- **Containers**: View all containers, start/stop/delete/view details
- **Images**: View all images with repository, tag, size, creation time
- **User Management**: Create/edit/delete API Keys, modify name, role, permissions, and scope
- **Audit Log**: View all operation records
- **Settings**: Edit system settings (port, timezone, feature toggles), change admin password
- **About**: View project info, config examples, version info

## First Login

- Default username: `admin`
- Default password: See the config file generated on first start (`secrets/admin.yaml`)
- We recommend changing the password immediately after login

## Container Status Colors

Container status in the list is color-coded:

- 🟢 **Green**: Running
- 🔴 **Red**: Restarting / Dead / Unhealthy
- ⚪ **Gray**: Exited / Created / Paused
