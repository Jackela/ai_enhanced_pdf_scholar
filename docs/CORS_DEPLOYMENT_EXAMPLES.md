# CORS Security Deployment Examples

This document provides ready-to-use deployment configuration examples for various platforms with the new secure CORS implementation.

## 🚀 Quick Deployment Checklist

Before deploying to any environment, ensure:

- [ ] `ENVIRONMENT` variable is set correctly
- [ ] `CORS_ORIGINS` contains only necessary, exact origins
- [ ] No wildcard (`*`) origins are used
- [ ] Production uses HTTPS origins only
- [ ] No localhost/127.0.0.1 origins in production
- [ ] Origins are comma-separated without spaces

## Docker Deployments

### Docker Compose - Development
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  api:
    build: .
    environment:
      - ENVIRONMENT=development
      - CORS_ORIGINS=http://localhost:3000,http://localhost:8080
      - DEBUG=true
    ports:
      - "8000:8000"
    
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - api
```

### Docker Compose - Production
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    build: .
    environment:
      - ENVIRONMENT=production
      - CORS_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com
      - DEBUG=false
    ports:
      - "8000:8000"
    restart: unless-stopped
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
```

### Dockerfile with Build Args
```dockerfile
# Dockerfile
FROM python:3.11-slim

ARG ENVIRONMENT=production
ARG CORS_ORIGINS

ENV ENVIRONMENT=${ENVIRONMENT}
ENV CORS_ORIGINS=${CORS_ORIGINS}

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt

CMD ["python", "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build with:
```bash
# Development
docker build --build-arg ENVIRONMENT=development \
             --build-arg CORS_ORIGINS=http://localhost:3000 \
             -t myapp:dev .

# Production  
docker build --build-arg ENVIRONMENT=production \
             --build-arg CORS_ORIGINS=https://app.yourdomain.com \
             -t myapp:prod .
```

## Kubernetes Deployments

### Development Namespace
```yaml
# k8s-dev.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-dev
  namespace: development
data:
  ENVIRONMENT: "development"
  CORS_ORIGINS: "http://localhost:3000,http://dev-frontend:3000"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-deployment
  namespace: development
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: myapp:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: app-config-dev
```

### Production Namespace
```yaml
# k8s-prod.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets-prod
  namespace: production
type: Opaque
stringData:
  CORS_ORIGINS: "https://app.yourdomain.com,https://admin.yourdomain.com"

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-prod
  namespace: production
data:
  ENVIRONMENT: "production"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-deployment
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: myapp:prod
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: app-config-prod
        - secretRef:
            name: app-secrets-prod
        livenessProbe:
          httpGet:
            path: /api/system/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

### Helm Chart Values
```yaml
# values.yaml
environment: production

cors:
  origins: 
    - "https://app.yourdomain.com"
    - "https://admin.yourdomain.com"

# values-dev.yaml
environment: development

cors:
  origins:
    - "http://localhost:3000"
    - "http://localhost:8080"
```

## Cloud Platform Deployments

### AWS ECS
```json
{
  "family": "ai-pdf-scholar",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "your-registry/ai-pdf-scholar:latest",
      "memory": 512,
      "cpu": 256,
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "CORS_ORIGINS", 
          "value": "https://app.yourdomain.com,https://admin.yourdomain.com"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ai-pdf-scholar",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "networkMode": "awsvpc",
  "cpu": "256",
  "memory": "512"
}
```

### AWS Lambda (with Mangum)
```python
# lambda_handler.py
import os
from mangum import Mangum

# Set CORS configuration for Lambda
os.environ['ENVIRONMENT'] = 'production'
os.environ['CORS_ORIGINS'] = 'https://your-cloudfront-domain.amazonaws.com'

from backend.api.main import app

handler = Mangum(app)
```

Environment variables in Lambda:
```json
{
  "Environment": {
    "Variables": {
      "ENVIRONMENT": "production",
      "CORS_ORIGINS": "https://your-cloudfront-domain.amazonaws.com"
    }
  }
}
```

### Google Cloud Run
```yaml
# service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ai-pdf-scholar-api
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containerConcurrency: 80
      timeoutSeconds: 300
      containers:
      - image: gcr.io/your-project/ai-pdf-scholar:latest
        ports:
        - name: http1
          containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: CORS_ORIGINS
          value: "https://app.yourdomain.com"
        resources:
          limits:
            cpu: "1000m"
            memory: "512Mi"
```

### Azure Container Instances
```yaml
# aci-deployment.yaml
apiVersion: 2019-12-01
location: eastus
name: ai-pdf-scholar-api
properties:
  containers:
  - name: api
    properties:
      image: your-registry.azurecr.io/ai-pdf-scholar:latest
      ports:
      - port: 8000
        protocol: TCP
      environmentVariables:
      - name: ENVIRONMENT
        value: production
      - name: CORS_ORIGINS
        secureValue: https://app.yourdomain.com,https://admin.yourdomain.com
      resources:
        requests:
          cpu: 1.0
          memoryInGb: 1.0
  osType: Linux
  ipAddress:
    type: Public
    ports:
    - protocol: TCP
      port: 8000
```

### Heroku
```bash
# Set config vars
heroku config:set ENVIRONMENT=production
heroku config:set CORS_ORIGINS=https://myapp.herokuapp.com

# For review apps
heroku config:set ENVIRONMENT=staging
heroku config:set CORS_ORIGINS=https://myapp-pr-123.herokuapp.com
```

Procfile:
```
web: python -m uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT
```

### Railway
```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
healthcheckPath = "/api/system/health"
healthcheckTimeout = 100
restartPolicyType = "always"

[[deploy.environmentVariables]]
name = "ENVIRONMENT"
value = "production"

[[deploy.environmentVariables]]
name = "CORS_ORIGINS"
value = "https://myapp.up.railway.app"
```

### Vercel (Serverless)
```json
{
  "functions": {
    "backend/api/main.py": {
      "runtime": "python3.9"
    }
  },
  "env": {
    "ENVIRONMENT": "production",
    "CORS_ORIGINS": "https://myapp.vercel.app"
  },
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "/backend/api/main.py"
    }
  ]
}
```

## Traditional Server Deployments

### Systemd Service
```ini
# /etc/systemd/system/ai-pdf-scholar.service
[Unit]
Description=AI PDF Scholar API
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/ai-pdf-scholar
Environment=ENVIRONMENT=production
Environment=CORS_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com
ExecStart=/opt/ai-pdf-scholar/venv/bin/python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy
```nginx
# /etc/nginx/sites-available/ai-pdf-scholar
server {
    listen 80;
    server_name app.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name app.yourdomain.com;

    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers are handled by the FastAPI app
        # No need to add CORS headers in Nginx
    }
    
    location / {
        # Serve frontend
        root /var/www/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

### Apache Virtual Host
```apache
# /etc/apache2/sites-available/ai-pdf-scholar.conf
<VirtualHost *:80>
    ServerName app.yourdomain.com
    Redirect permanent / https://app.yourdomain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName app.yourdomain.com
    
    SSLEngine on
    SSLCertificateFile /path/to/certificate.crt
    SSLCertificateKeyFile /path/to/private.key
    
    ProxyPreserveHost On
    ProxyPass /api/ http://127.0.0.1:8000/
    ProxyPassReverse /api/ http://127.0.0.1:8000/
    
    DocumentRoot /var/www/frontend/dist
    <Directory /var/www/frontend/dist>
        AllowOverride All
        Require all granted
        FallbackResource /index.html
    </Directory>
</VirtualHost>
```

## CI/CD Pipeline Examples

### GitHub Actions
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to staging
      run: |
        docker build \
          --build-arg ENVIRONMENT=staging \
          --build-arg CORS_ORIGINS="${{ secrets.STAGING_CORS_ORIGINS }}" \
          -t myapp:staging .
        
        # Deploy to staging environment
        
  deploy-production:
    runs-on: ubuntu-latest
    environment: production
    needs: deploy-staging
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to production
      run: |
        docker build \
          --build-arg ENVIRONMENT=production \
          --build-arg CORS_ORIGINS="${{ secrets.PRODUCTION_CORS_ORIGINS }}" \
          -t myapp:production .
        
        # Deploy to production environment
```

Repository Secrets:
- `STAGING_CORS_ORIGINS`: `https://staging.yourdomain.com`
- `PRODUCTION_CORS_ORIGINS`: `https://app.yourdomain.com,https://admin.yourdomain.com`

### GitLab CI
```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy-staging  
  - deploy-production

variables:
  DOCKER_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

build:
  stage: build
  script:
    - docker build -t $DOCKER_IMAGE .
    - docker push $DOCKER_IMAGE

deploy-staging:
  stage: deploy-staging
  environment: staging
  variables:
    ENVIRONMENT: staging
    CORS_ORIGINS: https://staging.yourdomain.com
  script:
    - kubectl set env deployment/api ENVIRONMENT=$ENVIRONMENT
    - kubectl set env deployment/api CORS_ORIGINS="$CORS_ORIGINS"
    - kubectl set image deployment/api api=$DOCKER_IMAGE

deploy-production:
  stage: deploy-production
  environment: production
  when: manual
  variables:
    ENVIRONMENT: production
    CORS_ORIGINS: https://app.yourdomain.com,https://admin.yourdomain.com
  script:
    - kubectl set env deployment/api ENVIRONMENT=$ENVIRONMENT
    - kubectl set env deployment/api CORS_ORIGINS="$CORS_ORIGINS"
    - kubectl set image deployment/api api=$DOCKER_IMAGE
```

## Environment-Specific Examples

### Multi-Tenant SaaS
```bash
# Tenant-specific origins
ENVIRONMENT=production
CORS_ORIGINS=https://tenant1.yourdomain.com,https://tenant2.yourdomain.com,https://admin.yourdomain.com
```

### Mobile App + Web App
```bash
# Support both web and mobile origins
ENVIRONMENT=production
CORS_ORIGINS=https://webapp.yourdomain.com,https://mobile-app.yourdomain.com
```

### Microservices Architecture
```bash
# API Gateway pattern
ENVIRONMENT=production
CORS_ORIGINS=https://gateway.yourdomain.com

# Direct service access
ENVIRONMENT=staging
CORS_ORIGINS=https://staging-frontend.yourdomain.com,https://staging-admin.yourdomain.com
```

### CDN/CloudFront Setup
```bash
# CloudFront distribution
ENVIRONMENT=production
CORS_ORIGINS=https://d1234567890123.cloudfront.net

# Custom domain through CloudFront
ENVIRONMENT=production
CORS_ORIGINS=https://app.yourdomain.com
```

## Testing Deployment

### Health Check Script
```bash
#!/bin/bash
# test-cors-deployment.sh

API_URL="https://your-api.com"
FRONTEND_URL="https://your-frontend.com"

echo "Testing CORS configuration..."

# Test allowed origin
response=$(curl -s -H "Origin: $FRONTEND_URL" \
               -H "Access-Control-Request-Method: GET" \
               -X OPTIONS "$API_URL/api/system/health")

if echo "$response" | grep -q "Access-Control-Allow-Origin: $FRONTEND_URL"; then
    echo "✅ Allowed origin works correctly"
else
    echo "❌ Allowed origin failed"
fi

# Test disallowed origin
response=$(curl -s -H "Origin: https://malicious.com" \
               -H "Access-Control-Request-Method: GET" \
               -X OPTIONS "$API_URL/api/system/health")

if echo "$response" | grep -q "Access-Control-Allow-Origin: https://malicious.com"; then
    echo "❌ SECURITY ISSUE: Malicious origin was allowed"
else
    echo "✅ Malicious origin correctly blocked"
fi

echo "CORS deployment test complete"
```

### Automated Testing
```python
# test_deployed_cors.py
import requests
import os

def test_deployed_cors():
    api_url = os.environ["API_URL"]
    allowed_origin = os.environ["ALLOWED_ORIGIN"]
    
    # Test allowed origin
    response = requests.options(
        f"{api_url}/api/system/health",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET"
        }
    )
    
    assert response.headers.get("Access-Control-Allow-Origin") == allowed_origin
    
    # Test disallowed origin
    response = requests.options(
        f"{api_url}/api/system/health", 
        headers={
            "Origin": "https://malicious.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    
    assert response.headers.get("Access-Control-Allow-Origin") != "https://malicious.com"
    print("✅ Deployed CORS configuration is secure")

if __name__ == "__main__":
    test_deployed_cors()
```

## Troubleshooting Common Issues

### Issue 1: CORS Still Not Working
```bash
# Check environment variables are set
echo "Environment: $ENVIRONMENT"
echo "CORS Origins: $CORS_ORIGINS"

# Check application logs for CORS configuration
docker logs container-name | grep CORS
```

### Issue 2: Frontend Can't Connect
```javascript
// Check browser console for CORS errors
fetch('/api/system/health')
  .then(response => console.log('Success:', response))
  .catch(error => console.error('CORS Error:', error));
```

### Issue 3: Production Security Validation Fails
```bash
# Common fixes:
export CORS_ORIGINS="https://app.yourdomain.com"  # Remove http://
export CORS_ORIGINS="https://app.yourdomain.com"  # Remove localhost
export CORS_ORIGINS="https://app.yourdomain.com"  # Remove wildcard *
```

---

**Security Note:** Always test your CORS configuration before deploying to production. Use the provided testing scripts to verify that only intended origins can access your API.

**Last Updated:** 2025-01-19  
**Version:** 2.0.0