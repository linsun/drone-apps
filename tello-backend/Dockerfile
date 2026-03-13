FROM python:3.12-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY tello_proxy_adapter.py .
COPY backend_http_server.py .
COPY backend_mcp_server.py .
COPY github_pr.py .
COPY start_backend.sh .

# Make startup script executable
RUN chmod +x start_backend.sh

# Expose ports for HTTP API and MCP server
EXPOSE 3001 3002

# Run both backend servers
CMD ["./start_backend.sh"]
