# GitHub PR endpoint (`POST /api/github-pr`)

The frontend calls this after AI analysis to create a PR in a GitHub repo with photo1, photo2, and the analysis result.

## Flow

1. **Branch**: Create branch `drone-capture-{timestamp}` from `main` (via GitHub MCP if `GITHUB_MCP_SERVER_URL` is set, else GitHub API).
2. **Markdown**: Add `captures/{timestamp}/analysis.md` with AI analysis text (MCP or API).
3. **Images**: Add `photo1.jpg` and `photo2.jpg` via **GitHub REST API only** (MCP doesn’t handle binary).
4. **PR**: Create pull request via GitHub API.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | **Yes** | GitHub Personal Access Token (or fine-grained token) with `repo` scope. Used for branch/file/PR when MCP is not used, and always for images and PR. |
| `GITHUB_MCP_SERVER_URL` | No | e.g. `http://agentgateway.mcp.svc.cluster.local:3000/mcp`. If set, branch creation and analysis markdown are done via MCP; images and PR still use GitHub API. |

## Kubernetes

Add to your backend Deployment `env`:

```yaml
env:
- name: GITHUB_TOKEN
  valueFrom:
    secretKeyRef:
      name: github-token
      key: token
- name: GITHUB_MCP_SERVER_URL
  value: "http://agentgateway.mcp.svc.cluster.local:3000/mcp"  # optional
```

Create the secret (e.g. from a classic PAT):

```bash
kubectl create secret generic github-token --from-literal=token=ghp_xxxx
```

## Request/response

- **Request**: `POST /api/github-pr`, JSON body: `repo`, `photo1Base64`, `photo2Base64`, `comparisonResult`.
- **Success**: `200`, `{ "success": true, "prUrl": "https://github.com/owner/repo/pull/123" }`.
- **Error**: `4xx/5xx`, `{ "success": false, "error": "message" }`.

Reference: [gen-ai-demo 4_Analyze_Engagement.py](https://github.com/linsun/gen-ai-demo/blob/main/demo/pages/4_Analyze_Engagement.py).
