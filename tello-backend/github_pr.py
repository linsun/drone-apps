"""
GitHub PR creation for Tello frontend: submit photo1, photo2, and LLaVA/Qwen3-VL
analysis to a repo as a new branch and open a PR.

Uses GitHub MCP server for branch + markdown (create_branch, create_or_update_file).
Uses GitHub REST API with GITHUB_TOKEN for binary images and for creating the PR
(since MCP doesn't handle images and may not expose create_pull_request).

Ref: https://github.com/linsun/gen-ai-demo/blob/main/demo/pages/4_Analyze_Engagement.py
"""

import os
import json
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

GITHUB_MCP_SERVER_URL = os.getenv("GITHUB_MCP_SERVER_URL", "")  # e.g. http://agentgateway.mcp.svc.cluster.local:3000/mcp
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_PR_EVENT_NAME = os.getenv("GITHUB_PR_EVENT_NAME", "").strip()  # e.g. "field-day-2025"; if empty, use timestamp
GITHUB_API_BASE = "https://api.github.com"

# Session state for MCP
_github_mcp_initialized = False
_github_mcp_session_id = None


def _parse_repo(repo_slug):
    """e.g. 'linsun/drone-demo' -> ('linsun', 'drone-demo')"""
    parts = repo_slug.strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid repo slug: {repo_slug}")
    return parts[0], parts[1]


def _initialize_github_mcp_session():
    global _github_mcp_session_id
    if not GITHUB_MCP_SERVER_URL:
        return False
    try:
        init_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "tello-backend-github-pr", "version": "1.0.0"},
            },
        }
        response = requests.post(
            GITHUB_MCP_SERVER_URL,
            json=init_request,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            timeout=30,
        )
        if response.status_code != 200:
            return False
        _github_mcp_session_id = response.headers.get("mcp-session-id")
        return True
    except Exception as e:
        logger.warning("GitHub MCP init failed: %s", e)
        return False


def _call_github_mcp_tool(tool_name, arguments):
    global _github_mcp_initialized, _github_mcp_session_id
    if not GITHUB_MCP_SERVER_URL:
        return None
    if not _github_mcp_initialized:
        if _initialize_github_mcp_session():
            _github_mcp_initialized = True
        else:
            return None
    try:
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if _github_mcp_session_id:
            headers["mcp-session-id"] = _github_mcp_session_id
        timeout = 120 if tool_name in ("create_branch", "create_or_update_file", "list_branches") else 60
        response = requests.post(GITHUB_MCP_SERVER_URL, json=mcp_request, headers=headers, timeout=timeout)
        if response.status_code != 200:
            return None
        ct = response.headers.get("content-type", "")
        if "text/event-stream" in ct:
            for line in response.text.strip().split("\n"):
                if line.startswith("data: "):
                    response_data = json.loads(line[6:])
                    break
            else:
                return None
        else:
            response_data = response.json()
        if "error" in response_data:
            return None
        return response_data.get("result")
    except Exception as e:
        logger.warning("MCP tool %s failed: %s", tool_name, e)
        return None


def _github_api_headers():
    # "token" for classic PAT; use "Bearer" for fine-grained / OAuth if needed
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def _get_main_sha(owner, repo):
    """Get the SHA of the main branch."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/main"
    resp = requests.get(url, headers=_github_api_headers(), timeout=15)
    if resp.status_code != 200:
        # try master
        resp = requests.get(url.replace("/heads/main", "/heads/master"), headers=_github_api_headers(), timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Could not get default branch: {resp.status_code} {resp.text[:200]}")
    return resp.json()["object"]["sha"]


def _create_branch_api(owner, repo, branch_name, base_sha):
    """Create a branch using GitHub API (refs)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs"
    body = {"ref": f"refs/heads/{branch_name}", "sha": base_sha}
    resp = requests.post(url, json=body, headers=_github_api_headers(), timeout=15)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Create branch failed: {resp.status_code} {resp.text[:200]}")
    return True


def _get_file_sha(owner, repo, path, branch):
    """Get the blob SHA of a file on the given branch, or None if the file does not exist."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=_github_api_headers(), params={"ref": branch}, timeout=15)
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        return None
    data = resp.json()
    if isinstance(data, list):
        return None  # path is a directory
    return data.get("sha")


def _create_or_update_file_api(owner, repo, path, content_base64, message, branch):
    """Create or update a file via GitHub Contents API. content_base64 is raw base64 string.
    If the file already exists on the branch (e.g. from a previous run with same event name),
    we must supply its sha for the update to succeed."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    body = {"message": message, "content": content_base64, "branch": branch}
    existing_sha = _get_file_sha(owner, repo, path, branch)
    if existing_sha:
        body["sha"] = existing_sha
    resp = requests.put(url, json=body, headers=_github_api_headers(), timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Create file {path} failed: {resp.status_code} {resp.text[:200]}")
    return True


def _create_pull_request_api(owner, repo, head_branch, base_branch, title, body):
    """Create a pull request."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
    payload = {"title": title, "head": head_branch, "base": base_branch, "body": body or ""}
    resp = requests.post(url, json=payload, headers=_github_api_headers(), timeout=15)
    if resp.status_code != 201:
        raise RuntimeError(f"Create PR failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    return data.get("html_url"), data.get("number")


def create_pr_payload(repo_slug, photo1_base64, photo2_base64, comparison_llava, comparison_qwen):
    """
    Create a new branch, add photo1.jpg, photo2.jpg, analysis.md, and open a PR.

    Returns dict: { "success": bool, "prUrl": str | None, "error": str | None }
    """
    if not GITHUB_TOKEN:
        return {"success": False, "prUrl": None, "error": "GITHUB_TOKEN is not set"}

    try:
        owner, repo = _parse_repo(repo_slug)
    except ValueError as e:
        return {"success": False, "prUrl": None, "error": str(e)}

    try:
        return _create_pr_impl(owner, repo, photo1_base64, photo2_base64, comparison_llava, comparison_qwen)
    except Exception as e:
        logger.exception("create_pr_payload failed")
        return {"success": False, "prUrl": None, "error": str(e)}


def _create_pr_impl(owner, repo, photo1_base64, photo2_base64, comparison_llava, comparison_qwen):
    import base64
    import re

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    if GITHUB_PR_EVENT_NAME:
        # Sanitize for branch/folder: alphanumeric, hyphens, underscores only
        event_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", GITHUB_PR_EVENT_NAME).strip("-") or timestamp
    else:
        event_slug = timestamp
    branch_name = f"drone-capture-{event_slug}"
    folder = f"captures/{event_slug}"
    base_branch = "main"

    # Get base SHA (needed for API branch create / fallback)
    base_sha = _get_main_sha(owner, repo)

    # 1) Create branch: MCP first, else API
    if GITHUB_MCP_SERVER_URL:
        mcp_result = _call_github_mcp_tool("create_branch", {
            "owner": owner,
            "repo": repo,
            "branch": branch_name,
            "from_branch": base_branch,
        })
        if mcp_result:
            logger.info("Branch created via MCP: %s", branch_name)
        else:
            _create_branch_api(owner, repo, branch_name, base_sha)
            logger.info("Branch created via API: %s", branch_name)
    else:
        _create_branch_api(owner, repo, branch_name, base_sha)
        logger.info("Branch created via API: %s", branch_name)

    # 2) Analysis markdown: photos side by side at top, then LLaVA and Qwen sections
    analysis_content = f"""# Drone/Webcam capture analysis – {event_slug}

| Photo 1 | Photo 2 |
|---------|---------|
| ![Photo 1](photo1.jpg) | ![Photo 2](photo2.jpg) |

## LLaVA

{comparison_llava or "(no response)"}

## Qwen3-VL

{comparison_qwen or "(no response)"}

"""
    analysis_b64 = base64.b64encode(analysis_content.encode("utf-8")).decode("ascii")
    analysis_path = f"{folder}/analysis.md"
    analysis_message = f"Add analysis for capture {event_slug}"

    if GITHUB_MCP_SERVER_URL:
        mcp_result = _call_github_mcp_tool("create_or_update_file", {
            "owner": owner,
            "repo": repo,
            "path": analysis_path,
            "content": analysis_content,
            "message": analysis_message,
            "branch": branch_name,
        })
        if not mcp_result:
            _create_or_update_file_api(owner, repo, analysis_path, analysis_b64, analysis_message, branch_name)
    else:
        _create_or_update_file_api(owner, repo, analysis_path, analysis_b64, analysis_message, branch_name)

    # 3) Images: GitHub API only (MCP doesn't handle binary)
    for name, b64 in (("photo1.jpg", photo1_base64), ("photo2.jpg", photo2_base64)):
        if not b64:
            continue
        path = f"{folder}/{name}"
        _create_or_update_file_api(
            owner, repo, path, b64,
            f"Add {name} for capture {event_slug}",
            branch_name,
        )
        logger.info("Uploaded %s via API", path)

    # 4) Create PR via API
    pr_title = f"Drone capture {event_slug}"
    pr_body = f"Photos and LLaVA/Qwen3-VL analysis from Tello frontend.\n\n- `{folder}/photo1.jpg`\n- `{folder}/photo2.jpg`\n- `{folder}/analysis.md`"
    pr_url, pr_number = _create_pull_request_api(owner, repo, branch_name, base_branch, pr_title, pr_body)
    logger.info("PR created: #%s %s", pr_number, pr_url)

    return {"success": True, "prUrl": pr_url, "error": None}
