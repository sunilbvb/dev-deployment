# Installation & Setup Guide 🛠️

The Dev Deployment Console is a zero-dependency, local-first developer tool. It requires no package managers (`pip`, `npm`) and runs directly on standard Python ≥ 3.10.

---

## 🚀 Quickstart (30 Seconds)

### 1. Clone the Repository
```bash
git clone https://github.com/sunilbvb/dev-deployment.git
cd dev-deployment
```

### 2. Launch the Console
```bash
./start.sh
```
*The script checks your Python version (≥ 3.10), verifies network bindings, generates an ephemeral or persistent bearer auth token, and opens the console in your default web browser.*

### 3. Alternative: Direct Python Execution
```bash
python3 features/deployment/backend/server.py --port 18112
```

---

## 💻 1-Click Desktop & System Service Installation

### Native Linux Desktop Shortcut
Create an application launcher in your desktop application menu (`~/.local/share/applications/dev-deployment.desktop`):
```bash
curl -s -X POST -H "X-API-Token: $(cat ~/.config/dev-deployment/auth_token.txt)" \
  http://localhost:18112/api/deployment/server/install-desktop
```
*Or click **Server Setup** in the console header and click **Install Desktop App**.*

### Systemd User Login Service
Configure the backend server to launch automatically on login as a background user daemon:
```bash
curl -s -X POST -H "X-API-Token: $(cat ~/.config/dev-deployment/auth_token.txt)" \
  http://localhost:18112/api/deployment/server/install-service
```
*This installs and activates `~/.config/systemd/user/dev-deployment.service`.*

---

## ⚙️ Configuration & Options

| CLI Flag | Default | Description |
|:---|:---|:---|
| `--port <num>` | `18112` | Network port for local HTTP server |
| `--host <ip>` | `127.0.0.1` | Binding interface (defaults to loopback for security) |
| `--workspace <dir>` | Current directory | Initial project directory to load |

---

## 🔒 Security & Auth Token
The server enforces local bearer authentication. The access token is stored with `chmod 600` permissions at:
```bash
~/.config/dev-deployment/auth_token.txt
```
All UI requests include this token automatically via `X-API-Token` header.
