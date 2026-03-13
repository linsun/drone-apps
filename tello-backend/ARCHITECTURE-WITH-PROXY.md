# Architecture: K8s Backend + Mac Tello Proxy

## Recommended Setup

This architecture separates network concerns and provides the most reliable setup:

```
┌─────────────────────────────────────────────────┐
│  Frontend (K8s)                                  │
│  - React/Vue/etc app                            │
│  - Calls Backend API                            │
└─────────────────┬───────────────────────────────┘
                  │ HTTP
                  ↓
┌─────────────────────────────────────────────────┐
│  Backend (K8s)                                   │
│  - Business logic                               │
│  - MCP server                                   │
│  - Calls Tello Proxy                            │
└─────────────────┬───────────────────────────────┘
                  │ HTTP to host.docker.internal:5000
                  ↓
┌─────────────────────────────────────────────────┐
│  Tello Proxy Service (Mac - Native)             │
│  - Lightweight Flask app                        │
│  - Direct WiFi access to Tello                  │
│  - HTTP → UDP translation                       │
└─────────────────┬───────────────────────────────┘
                  │ UDP
                  ↓
┌─────────────────────────────────────────────────┐
│  Tello Drone (192.168.10.1)                     │
└─────────────────────────────────────────────────┘
```

## Why This is Better

### Problems with Direct K8s → Tello:
- ❌ Docker/K8s networking isolation
- ❌ `hostNetwork: true` doesn't work on Mac
- ❌ Complex UDP forwarding needed
- ❌ Unreliable across K8s environments

### Benefits of Proxy Approach:
- ✅ Clean separation of concerns
- ✅ Mac has direct WiFi access (no Docker issues)
- ✅ Simple HTTP API between services
- ✅ Backend can restart without affecting Tello
- ✅ Works on any K8s (Mac, Linux, Cloud)
- ✅ Easy to test and debug

## Setup Instructions

### Step 1: Start Tello Proxy on Mac

```bash
cd ~/src/github.com/linsun/tello-backend

# Install dependencies
pip3 install flask flask-cors

# Start the proxy service
python3 tello-proxy-service.py
```

Expected output:
```
🚁 Tello Proxy Service Starting...
==================================================
✅ Tello reachable at 192.168.10.1
✅ Sockets initialized
📡 State receiver thread started
🌐 Starting HTTP server on http://0.0.0.0:5000
```

**Keep this terminal running!**

### Step 2: Update Backend to Use Proxy

Update your backend code to call the proxy instead of djitellopy:

**Option A: Modify existing backend**

Change the backend to make HTTP calls to `http://host.docker.internal:5000` instead of using djitellopy directly.

**Option B: Use proxy with existing code**

Set environment variable to point djitellopy to the proxy... Actually, djitellopy expects UDP, so we need a different approach.

### Step 3: Deploy Backend to K8s

Update `k8s-deployment.yaml` to use the proxy:

```yaml
env:
- name: TELLO_PROXY_URL
  value: "http://host.docker.internal:5000"
```

### Step 4: Deploy Frontend to K8s

Your frontend calls the backend service in K8s:

```yaml
env:
- name: BACKEND_URL
  value: "http://tello-backend:3001"
```

## API Reference: Tello Proxy Service

The proxy service exposes these endpoints:

### POST /tello/connect
Connect to Tello (enter SDK mode)

**Request:**
```bash
curl -X POST http://localhost:5000/tello/connect
```

**Response:**
```json
{
  "success": true,
  "message": "Connected to Tello",
  "battery": "87"
}
```

### POST /tello/command
Send raw command to Tello

**Request:**
```bash
curl -X POST http://localhost:5000/tello/command \
  -H "Content-Type: application/json" \
  -d '{"command": "takeoff"}'
```

**Response:**
```json
{
  "success": true,
  "response": "ok",
  "command": "takeoff"
}
```

### GET /tello/state
Get current Tello state

**Request:**
```bash
curl http://localhost:5000/tello/state
```

**Response:**
```json
{
  "success": true,
  "state": {
    "bat": "87",
    "pitch": "0",
    "roll": "0",
    "yaw": "0",
    "h": "0",
    "tof": "10"
  }
}
```

### GET /tello/battery
Get battery level

**Request:**
```bash
curl http://localhost:5000/tello/battery
```

**Response:**
```json
{
  "success": true,
  "battery": 87
}
```

### GET /health
Health check

**Request:**
```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "healthy",
  "connected_to_tello": true,
  "last_state_update": 0.5
}
```

## Testing from K8s Pod

Once the proxy is running on Mac and your backend is deployed:

```bash
# Get into backend pod
kubectl exec -it <backend-pod> -- /bin/bash

# Test proxy connectivity
curl http://host.docker.internal:5000/health

# Connect to Tello via proxy
curl -X POST http://host.docker.internal:5000/tello/connect

# Send command
curl -X POST http://host.docker.internal:5000/tello/command \
  -H "Content-Type: application/json" \
  -d '{"command": "battery?"}'
```

## Integration Options

### Option 1: Minimal Changes (Adapter Pattern)

Create an adapter in your backend that translates djitellopy calls to HTTP proxy calls:

```python
import requests
import os

class TelloProxyAdapter:
    def __init__(self):
        self.proxy_url = os.getenv('TELLO_PROXY_URL', 'http://host.docker.internal:5000')

    def connect(self):
        response = requests.post(f'{self.proxy_url}/tello/connect')
        return response.json()

    def send_command(self, command):
        response = requests.post(
            f'{self.proxy_url}/tello/command',
            json={'command': command}
        )
        return response.json()

    def get_battery(self):
        response = requests.get(f'{self.proxy_url}/tello/battery')
        return response.json()['battery']

# Use adapter instead of djitellopy
tello = TelloProxyAdapter()
```

### Option 2: Backend Talks to Proxy Only

Simplify your backend to just forward requests to the proxy. Backend becomes a thin wrapper that adds MCP protocol, authentication, etc.

### Option 3: Keep Current Backend Structure

If you want to keep using djitellopy in your backend, you'll need the UDP proxy approach we discussed earlier. But the HTTP proxy is cleaner.

## Deployment Checklist

- [ ] Mac connected to Tello WiFi
- [ ] Tello proxy service running on Mac (port 5000)
- [ ] Backend deployed to K8s with `TELLO_PROXY_URL` env var
- [ ] Backend can reach `host.docker.internal:5000`
- [ ] Frontend deployed to K8s
- [ ] Frontend can reach backend service

## Troubleshooting

### Proxy won't start
```bash
# Check if port 5000 is in use
lsof -i :5000

# Kill existing process
kill <PID>

# Try again
python3 tello-proxy-service.py
```

### Backend can't reach proxy
```bash
# Test from pod
kubectl exec -it <pod> -- curl http://host.docker.internal:5000/health

# If fails, check if host.docker.internal resolves
kubectl exec -it <pod> -- nslookup host.docker.internal
```

### Tello not responding
```bash
# From Mac, verify Tello connection
ping -c 3 192.168.10.1

# Check proxy logs for errors
# The proxy shows all commands/responses in real-time
```

## Production Considerations

For production/permanent setup:

1. **Run proxy as a service** (systemd, launchd, Docker)
2. **Add authentication** between backend and proxy
3. **Use persistent connection** in proxy (keep UDP sockets alive)
4. **Add metrics/monitoring** (Prometheus, etc.)
5. **Consider running everything on Linux** where hostNetwork works properly

## Alternative: Use Your Existing Backend on Mac

If you don't want to create a separate proxy, just run your existing `tello-backend` on Mac:

```bash
cd ~/src/github.com/linsun/tello-backend
export TELLO_IP=192.168.10.1
./start_servers.sh

# Runs on:
# - HTTP: localhost:3001
# - MCP: localhost:3002
```

Then your K8s services call `host.docker.internal:3001` instead.

This is even simpler but you lose the benefits of having the backend in K8s (scaling, monitoring, etc.).

## Summary

**Recommended approach:**
1. Lightweight Tello proxy on Mac (handles WiFi)
2. Full backend in K8s (handles business logic)
3. Frontend in K8s (user interface)

This gives you the best of both worlds: reliable Tello connectivity + K8s benefits.
