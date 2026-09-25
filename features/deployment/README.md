# Deployment Console Subsystem

Backend and frontend modules for the standalone Deployment Console.

> 📖 **Architecture & Deep Dive:** See [docs/README.md](docs/README.md) for job lifecycle, process management, build script integration, and API reference.

## Quick Run

Start server:
```bash
./bin/start-deployment.sh
```

Stop server:
```bash
./bin/stop-deployment.sh
```

Check status:
```bash
./bin/status-deployment.sh
```

Restart server:
```bash
./bin/restart-deployment.sh
```

Or run directly with Python:
```bash
python3 backend/server.py --port 18112
```

Open in browser:
```text
http://localhost:18112
```

## What This Subsystem Handles

1. **App Discovery**: Automatically detects apps from workspace folders (`apps/`, `packages/`, or root project manifests like `pubspec.yaml`, `package.json`, `build.gradle`).
2. **Command Dispatcher**: Cross-references apps with templates from `config/deployment_templates.json` to generate build and deployment commands.
3. **Real-Time Log Streaming**: Streams process output line-by-line into the web terminal.
4. **Safety Locks**: Prevents starting conflicting builds on the same app concurrently (`APP_BUSY`).
5. **Confirmation Gate**: Requires explicit confirmation before triggering production store releases.
6. **Deployment History**: Retains job run history, timestamps, and error excerpts across server restarts.
7. **CI/CD Webhook**: Accepts remote trigger requests via `/api/deployment/webhook`.
