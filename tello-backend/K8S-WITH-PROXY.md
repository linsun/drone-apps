# Kubernetes Deployment with host.docker.internal Proxy

## Overview

This setup allows your Kubernetes pod to connect to the Tello drone through a UDP proxy running on your Mac.

**Architecture:**
```
Tello (192.168.10.1)
    ↕ WiFi
Mac (connected to TELLO-XXXXXX)
    ↕ UDP Proxy (socat)
host.docker.internal
    ↕ Docker/K8s networking
Pod (tello-backend)
```

## Setup Steps

### 1. Connect to Tello WiFi

On your Mac, connect to the Tello WiFi network:
- Network name: `TELLO-XXXXXX`
- Wait for connection to establish
- Verify: `ping -c 3 192.168.10.1`

### 2. Start the UDP Proxy on Your Mac

Open a terminal and run:

```bash
cd tello-backend
python3 -m venv venv
source venv/bin/activate
# pip install flask flask-cors mcp opencv-python-headless djitellopy
./start-tello-proxy.sh
```

This will:
- Install `socat` if needed
- Check Tello connectivity
- Start UDP proxies on ports 8889, 8890, and 11111
- Forward traffic between your Mac and Tello

**Keep this terminal open!** The proxy must run while you're using the Tello.

### 3. Deploy to Kubernetes

In a **new terminal**, deploy the application:

```bash
cd ~/src/github.com/linsun/tello-backend

# Deploy to your K8s cluster
kubectl apply -f k8s-deployment.yaml

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=tello-backend --timeout=60s

# Check status
kubectl get pods -l app=tello-backend
kubectl logs -l app=tello-backend
```

### 4. Test the Connection

Using MCP Inspector:

```bash
npx @modelcontextprotocol/inspector sse http://localhost:30002/sse
```

In the inspector:
1. Tool: `connect` (or `connect_drone`)
2. Should return success with battery level
3. Try: `get_battery`
4. Try: `get_status`

Or test via HTTP API:

```bash
# Check status
curl http://localhost:30001/api/status

# Connect to Tello
curl -X POST http://localhost:30001/api/connect

# Get battery
curl http://localhost:30001/api/battery
```

## How It Works

### Environment Variable

The pod is configured with:
```yaml
env:
- name: TELLO_IP
  value: "host.docker.internal"
```

### DNS Resolution

- `host.docker.internal` is a special DNS name in Docker/K8s
- It resolves to your Mac's IP address as seen from the container
- On Docker Desktop: Usually `192.168.65.2` or `host-gateway`
- On Minikube: Resolves to the Minikube host VM

### UDP Proxy (socat)

The proxy script uses `socat` to forward UDP traffic:

```bash
# Command port (bidirectional)
socat UDP4-LISTEN:8889,fork,reuseaddr UDP4:192.168.10.1:8889

# State port (Tello → Pod)
socat UDP4-LISTEN:8890,fork,reuseaddr UDP4:192.168.10.1:8890

# Video port (Tello → Pod)
socat UDP4-LISTEN:11111,fork,reuseaddr UDP4:192.168.10.1:11111
```

### Traffic Flow

**Sending Commands:**
```
Pod → host.docker.internal:8889 → Mac:8889 → socat → Tello:8889
```

**Receiving State:**
```
Tello:8890 → Mac:8890 → socat → host.docker.internal:8890 → Pod
```

**Receiving Video:**
```
Tello:11111 → Mac:11111 → socat → host.docker.internal:11111 → Pod
```

## Troubleshooting

### Proxy won't start

```bash
# Check if ports are already in use
lsof -i :8889
lsof -i :8890
lsof -i :11111

# Kill any process using these ports
kill <PID>

# Try running proxy again
./run-tello-proxy.sh
```

### Pod can't resolve host.docker.internal

For Docker Desktop, this should work automatically.

For Minikube, you may need to add an extra host:

```bash
# Get your Mac's IP on the bridge network
DOCKER_HOST_IP=$(docker network inspect bridge --format='{{range .IPAM.Config}}{{.Gateway}}{{end}}')

# Update deployment to add host alias
kubectl patch deployment tello-backend --type='json' -p='[
  {
    "op": "add",
    "path": "/spec/template/spec/hostAliases",
    "value": [{"ip": "'$DOCKER_HOST_IP'", "hostnames": ["host.docker.internal"]}]
  }
]'
```

### Connection still fails

1. **Verify proxy is running:**
   ```bash
   ps aux | grep socat
   ```

2. **Test from Mac:**
   ```bash
   # Test UDP echo to Tello
   echo -n "command" | nc -u -w 1 192.168.10.1 8889
   # Should respond with "ok"
   ```

3. **Test from pod:**
   ```bash
   POD=$(kubectl get pod -l app=tello-backend -o jsonpath='{.items[0].metadata.name}')

   # Check if host.docker.internal resolves
   kubectl exec -it $POD -- nslookup host.docker.internal

   # Try to reach proxy
   kubectl exec -it $POD -- timeout 2 nc -u -z host.docker.internal 8889
   ```

4. **Check pod logs:**
   ```bash
   kubectl logs -f -l app=tello-backend
   ```

5. **Check proxy logs:**
   ```bash
   # The proxy script shows connection attempts in real-time
   # Look for "UDP4-LISTEN" lines in the terminal running the proxy
   ```

### Firewall issues

If you have a firewall enabled on your Mac:

```bash
# Temporarily disable to test
# System Settings → Network → Firewall → Turn Off

# Or add rules for ports 8889, 8890, 11111
```

### Different Kubernetes environments

**Docker Desktop:**
- `host.docker.internal` works by default ✅

**Minikube:**
- May need extra host configuration ⚠️
- See "Pod can't resolve host.docker.internal" above

**Kind:**
- `host.docker.internal` may not work ❌
- Use the Kind network gateway IP instead

**Remote K8s (AWS, GCP, etc.):**
- This approach won't work ❌
- The pod needs to be on the same network as your Mac
- Consider running the proxy as a sidecar container

## Stopping Everything

1. **Stop the proxy:**
   - Press `Ctrl+C` in the terminal running `run-tello-proxy.sh`
   - Or: `pkill -f "socat.*8889"`

2. **Stop the deployment:**
   ```bash
   kubectl delete -f k8s-deployment.yaml
   ```

3. **Verify cleanup:**
   ```bash
   ps aux | grep socat
   kubectl get pods -l app=tello-backend
   ```

## Advantages of This Approach

✅ Works on Mac with Docker Desktop K8s
✅ No need to modify application code
✅ Simple configuration change (just env var)
✅ Pod uses standard Tello IP logic
✅ Easy to switch between direct and proxied modes

## Limitations

⚠️ Requires proxy to be running on Mac
⚠️ Extra latency (Mac → Pod forwarding)
⚠️ Video streaming may have higher latency
⚠️ Only works when Mac is connected to Tello WiFi
⚠️ Doesn't work for remote K8s clusters

## Alternative: Direct Connection on Linux

If you deploy to a Linux-based K8s cluster where the node is connected to Tello WiFi:

1. Change `TELLO_IP` back to `192.168.10.1`
2. Keep `hostNetwork: true`
3. No proxy needed!

This is the recommended setup for production/permanent installations.

## Questions?

- Proxy not working? Check the troubleshooting section above
- Need help with specific K8s environment? See the environment-specific notes
- Want to run without proxy? Consider deploying to Linux or running directly on Mac
