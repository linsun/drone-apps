# Drone Apps

A web application for capturing photos from a DJI Tello drone (or webcam), comparing them with an AI vision model, and publishing the results to GitHub as a pull request.

## Architecture

```
Browser --> Frontend (React / Nginx) --> Backend (Flask / K8s)
                                            |
                              +-------------+-------------+
                              |             |             |
                        Tello Proxy    Ollama         GitHub API
                         (Mac UDP)   (qwen3-vl)       / MCP
                              |
                        Tello Drone
```

The frontend serves the React app and proxies `/api/*` requests to the backend via Nginx. The backend communicates with the Tello drone through a UDP proxy running on the host Mac, sends photos to a locally-running Ollama vision model for engagement analysis, and creates GitHub pull requests with the results.

## Features

- **Dual camera input** -- connect to a DJI Tello drone or use a browser webcam
- **Drone flight controls** -- takeoff, land, move, rotate, and flip
- **Live video streaming** -- MJPEG stream from the drone or webcam
- **Photo capture** -- capture two photos for side-by-side comparison
- **AI engagement analysis** -- score and compare photos using a vision model (qwen3-vl) via Ollama
- **Text-to-speech** -- reads the analysis summary aloud
- **GitHub PR creation** -- publishes photos and analysis to a GitHub repo as a pull request

## Project Structure

```
drone-apps/
├── tello-frontend/    # React frontend
└── tello-backend/     # Python Flask backend
```

### Frontend (`tello-frontend/`)

| Component | Details |
|-----------|---------|
| Framework | React 19, Create React App |
| Styling   | Tailwind CSS 3.4 |
| Icons     | Lucide React |
| Serving   | Nginx (in Docker), proxies `/api/*` to backend |

Key files:
- `src/App.js` -- main application (camera, capture, AI comparison, flight controls)
- `nginx.conf` -- Nginx config for production (API proxy + SPA routing)
- `Dockerfile` -- multi-stage build (Node build, then Nginx serve)
- `k8s-deployment.yaml` -- Kubernetes Deployment and Service

### Backend (`tello-backend/`)

| Component | Details |
|-----------|---------|
| Framework | Flask 3.0, flask-cors |
| AI model  | qwen3-vl via Ollama |
| Language  | Python 3.12 |

Key files:
- `backend_http_server.py` -- REST API (drone control, photo capture, AI comparison, GitHub PR)
- `backend_mcp_server.py` -- MCP server for AI agent integration
- `tello_proxy_adapter.py` -- adapter that talks to the Tello proxy over HTTP
- `github_pr.py` -- creates GitHub branches, uploads photos, opens PRs
- `Dockerfile` -- Python 3.12-slim image
- `k8s-deployment.yaml` -- Kubernetes Deployment and Service

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) and a Kubernetes cluster (e.g. Docker Desktop, kind, or minikube)
- [Ollama](https://ollama.com/) running locally with the vision model pulled:
  ```bash
  ollama pull qwen3-vl:4b
  ```
- A GitHub Personal Access Token (for PR creation)

### Deploy to Kubernetes

1. Create the GitHub token secret:
   ```bash
   kubectl create secret generic github-mcp-secret \
     --from-literal=GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxxx
   ```

2. Build and push the images:
   ```bash
   cd tello-backend && docker build -t linsun/tello-backend:latest . && cd ..
   cd tello-frontend && docker build -t linsun/tello-frontend:latest . && cd ..
   ```

3. Deploy:
   ```bash
   kubectl apply -f tello-backend/k8s-deployment.yaml
   kubectl apply -f tello-frontend/k8s-deployment.yaml
   ```

4. Access the frontend via the LoadBalancer IP or port-forward:
   ```bash
   kubectl port-forward svc/tello-frontend 8080:80
   ```
   Then open http://localhost:8080.

### Environment Variables

#### Backend

| Variable | Required | Description |
|----------|----------|-------------|
| `OLLAMA_URL` | No | Ollama API URL (default: `http://host.docker.internal:11434`) |
| `VISION_MODEL` | No | Vision model name (default: `qwen3-vl:4b`) |
| `TELLO_PROXY_URL` | No | Tello proxy URL (default: `http://host.docker.internal:50000`) |
| `GITHUB_TOKEN` | Yes | GitHub PAT for PR creation |
| `GITHUB_MCP_SERVER_URL` | No | GitHub MCP server URL (optional, for MCP-based branch/file creation) |
| `GITHUB_PR_EVENT_NAME` | No | Event name for PR branch/folder naming (e.g. `kubecon-eu-2026`) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Server and drone status |
| POST | `/api/connect` | Connect to drone |
| POST | `/api/disconnect` | Disconnect from drone |
| GET | `/api/battery` | Battery level |
| POST | `/api/takeoff` | Take off |
| POST | `/api/land` | Land |
| POST | `/api/move` | Move in a direction |
| POST | `/api/rotate` | Rotate clockwise/counterclockwise |
| POST | `/api/flip` | Flip in a direction |
| POST | `/api/start-stream` | Start video stream |
| POST | `/api/stop-stream` | Stop video stream |
| GET | `/api/video-feed` | MJPEG video stream |
| POST | `/api/capture` | Capture a photo |
| POST | `/api/compare-photos` | AI engagement comparison |
| POST | `/api/github-pr` | Create a GitHub PR with photos and analysis |

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
