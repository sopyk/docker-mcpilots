# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-07-03

### Added
- FastMCP-based MCP Server running in Docker container
- Container management MCP Tools (list/inspect/start/stop/restart/logs/stats/remove)
- Image management MCP Tools (list/pull/remove)
- System diagnostics MCP Tools (CPU/memory/disk/network/system info)
- RBAC permission system with admin/operator/observer roles
- Container-level scope access control (include/exclude wildcard patterns)
- API Key authentication via YAML config or environment variables
- Config and Secrets separation with persistent volume mounts
- Auto-generation of default config templates on first startup
- Health check endpoint (/health)
- Dockerfile and docker-compose.yml for Synology NAS deployment
