# Docker Setup Guide - KnowBot

## Files Created

1. **`Dockerfile`** (root) - Backend (FastAPI) Dockerfile
2. **`frontend/Dockerfile`** - Frontend (React) Dockerfile  
3. **`.dockerignore`** (root) - Excludes unnecessary files from backend build
4. **`frontend/.dockerignore`** - Excludes unnecessary files from frontend build
5. **`docker-compose.yml`** - Orchestrates both services

---

## Quick Start

### Prerequisites
- Docker installed
- Docker Compose installed
- `.env` file with all required environment variables (copy from `.env.example` if available)

### Run Both Services Together

```bash
# From project root
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Access:**
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:3001`
- API Docs: `http://localhost:3001/docs`
- Health Check: `http://localhost:3001/api/health`

---

## Build Images Individually

### Backend Only

```bash
# Build
docker build -t knowbot-backend:latest .

# Run
docker run -p 3001:3001 \
  -e AZURE_COSMOS_DB_CONN="your-connection-string" \
  -e AZURE_SEARCH_ENDPOINT="your-endpoint" \
  -e AZURE_SEARCH_ADMIN_KEY="your-key" \
  knowbot-backend:latest
```

### Frontend Only

```bash
# Build
cd frontend
docker build -t knowbot-frontend:latest .

# Run
docker run -p 3000:3000 \
  -e REACT_APP_API_URL=http://localhost:3001 \
  knowbot-frontend:latest
```

---

## Environment Variables

Create a `.env` file in the project root with:

```
# Azure Cosmos DB
AZURE_COSMOS_DB_CONN=your-connection-string
AZURE_COSMOS_DB=db-1
AZURE_COSMOS_CONTAINER=messages

# Azure Search
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_ADMIN_KEY=your-key

# Azure OpenAI Embeddings
AZURE_OPENAI_EMBED_API_KEY=your-key
AZURE_OPENAI_EMBED_API_VERSION=2024-02-15-preview
AZURE_OPENAI_EMBED_ENDPOINT=https://your-embed.openai.azure.com/
AZURE_OPENAI_EMBED_MODEL_NAME=text-embedding-3-small

# Azure OpenAI LLM
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-llm.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=your-key;...
```

---

## Common Commands

```bash
# Build fresh images
docker-compose build --no-cache

# View running containers
docker ps

# View specific container logs
docker logs knowbot-frontend
docker logs knowbot-backend

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Restart services
docker-compose restart

# Execute command in running container
docker exec knowbot-backend python -c "import sys; print(sys.version)"

# Push to registry (example)
docker tag knowbot-backend:latest myregistry.azurecr.io/knowbot-backend:latest
docker push myregistry.azurecr.io/knowbot-backend:latest
```

---

## Docker Image Details

### Backend Image
- **Base**: `python:3.11-slim`
- **Port**: 3001
- **Health Check**: Calls `/api/health` endpoint every 30s
- **Process**: Runs FastAPI with Uvicorn

### Frontend Image
- **Base**: `node:18-alpine` (2-stage build)
- **Port**: 3000
- **Health Check**: HTTP GET to port 3000 every 30s
- **Process**: Serves React build with `serve`

---

## Production Deployment Notes

### Azure Container Registry (ACR)

```bash
# Login to ACR
az acr login --name myregistry

# Build and push
az acr build --registry myregistry --image knowbot-backend:latest .
az acr build --registry myregistry --image knowbot-frontend:latest ./frontend
```

### Azure Container Instances (ACI)

```bash
# Find container group template in azure/ folder or generate with:
az container create --resource-group mygroup \
  --name knowbot \
  --image myregistry.azurecr.io/knowbot-backend:latest \
  --registry-login-server myregistry.azurecr.io \
  --registry-username admin \
  --registry-password <password> \
  --ports 3001 \
  --environment-variables AZURE_COSMOS_DB_CONN=xxx AZURE_SEARCH_ENDPOINT=xxx
```

### Azure Kubernetes Service (AKS)

Create `k8s-deployment.yaml` for orchestration (example):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowbot-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: knowbot-backend
  template:
    metadata:
      labels:
        app: knowbot-backend
    spec:
      containers:
      - name: backend
        image: myregistry.azurecr.io/knowbot-backend:latest
        ports:
        - containerPort: 3001
        env:
        - name: AZURE_COSMOS_DB_CONN
          valueFrom:
            secretKeyRef:
              name: knowbot-secrets
              key: cosmos-conn
```

---

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker logs knowbot-backend

# Common issues:
# 1. Missing .env file - create with all variables
# 2. Azure service unreachable - check connection strings
# 3. Port 3001 in use - change to different port
docker run -p 3002:3001 knowbot-backend:latest
```

### Frontend won't start
```bash
# Check logs
docker logs knowbot-frontend

# Common issues:
# 1. Port 3000 in use - change to different port
docker run -p 3001:3000 knowbot-frontend:latest
# 2. API URL not configured - set REACT_APP_API_URL env var
```

### Health check failures
- Wait 10 seconds after container starts (start_period setting)
- Verify service is actually responding on the port
- Check service logs for errors

---

## Performance Optimization

### Frontend Build Size
- Current: ~50-100MB (multi-stage reduces from ~200MB)
- Further reduce by removing unused npm packages

### Backend Image Size
- Current: ~150-200MB (python:3.11-slim)
- Can be reduced further with distroless images (not recommended for data science apps)

### Caching
- Docker layer caching helps with rebuilds
- Avoid `--no-cache` unless necessary

---

## Next Steps

1. Test locally with docker-compose
2. Push images to Azure Container Registry
3. Deploy to Azure Container Instances or AKS
4. Set up CI/CD pipeline (GitHub Actions, Azure DevOps)
5. Monitor with Application Insights
