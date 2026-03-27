# 🚀 AI Enhanced PDF Scholar - Production Deployment Guide

This guide provides comprehensive instructions for deploying AI Enhanced PDF Scholar in production environments.

---

## Table of Contents

1. [Deployment Options Overview](#deployment-options-overview)
2. [Docker Deployment](#docker-deployment)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Cloud Platform Deployment](#cloud-platform-deployment)
6. [Post-Deployment Configuration](#post-deployment-configuration)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)

---

## Deployment Options Overview

| Method | Best For | Complexity | Scalability |
|--------|----------|------------|-------------|
| **Docker Compose** | Single server, small teams | Low | Limited |
| **Kubernetes** | Enterprise, high availability | High | Excellent |
| **Manual Setup** | Development, custom setups | Medium | Manual |
| **Cloud Platforms** | Managed infrastructure | Low-Medium | Auto-scaling |

---

## Docker Deployment

### Prerequisites

- Docker Engine 24.0+
- Docker Compose 2.20+
- 4GB+ RAM available
- 10GB+ free disk space

### Quick Start with Docker Compose

```bash
# 1. Clone the repository
git clone https://github.com/Jackela/ai_enhanced_pdf_scholar.git
cd ai_enhanced_pdf_scholar

# 2. Configure environment
cp .env.example .env
# Edit .env with your production settings

# 3. Start production services
docker-compose --profile prod up -d

# 4. Verify deployment
curl http://localhost:8000/api/system/health
```

### Production Environment Variables

Create a `.env` file with these required variables:

```bash
# =============================================================================
# AI Enhanced PDF Scholar - Production Environment Configuration
# =============================================================================

# -----------------------------------------------------------------------------
# Core Application Settings
# -----------------------------------------------------------------------------
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=your-super-secret-key-change-this-in-production

# -----------------------------------------------------------------------------
# API Keys (Required for AI features)
# -----------------------------------------------------------------------------
GOOGLE_API_KEY=your-gemini-api-key-here
OPENAI_API_KEY=your-openai-api-key-here  # Optional

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------
# Option 1: SQLite (Simple, single-node)
DATABASE_URL=sqlite:///data/library.db

# Option 2: PostgreSQL (Recommended for production)
# DATABASE_URL=postgresql://user:password@postgres:5432/ai_pdf_scholar
# POSTGRES_USER=pdf_scholar
# POSTGRES_PASSWORD=secure-random-password
# POSTGRES_DATABASE=ai_pdf_scholar

# -----------------------------------------------------------------------------
# Redis Configuration (Optional but recommended)
# -----------------------------------------------------------------------------
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=your-redis-password

# -----------------------------------------------------------------------------
# File Storage Configuration
# -----------------------------------------------------------------------------
STORAGE_BASE_DIR=/app/data
MAX_FILE_SIZE_MB=100
MAX_DOCUMENTS=10000
PREVIEWS_ENABLED=true
PREVIEW_CACHE_DIR=/app/data/previews

# -----------------------------------------------------------------------------
# Security Settings
# -----------------------------------------------------------------------------
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
ALLOWED_HOSTS=yourdomain.com,app.yourdomain.com
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# -----------------------------------------------------------------------------
# SSL/TLS Configuration
# -----------------------------------------------------------------------------
# Enable if terminating TLS at the application (not recommended, use reverse proxy)
SSL_ENABLED=false
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/key.pem
```

### Docker Compose Production Profile

The production profile includes:
- **app-prod**: Main application container
- **nginx**: Reverse proxy with SSL termination
- **postgres**: PostgreSQL database (optional)
- **redis**: Redis cache (optional)

```bash
# Start only production services
docker-compose --profile prod up -d

# Start with database and cache
docker-compose --profile prod --profile data up -d

# View logs
docker-compose logs -f app-prod

# Scale application instances
docker-compose up -d --scale app-prod=3
```

### Docker Security Best Practices

1. **Run as non-root user** (already configured in Dockerfile)
2. **Use secrets management** for sensitive data:
   ```bash
   # Use Docker secrets
   echo "your-api-key" | docker secret create gemini_api_key -
   ```
3. **Enable resource limits**:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
         cpus: '1.5'
       reservations:
         memory: 512M
         cpus: '0.5'
   ```
4. **Keep images updated**:
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster 1.25+
- kubectl configured
- Helm 3.12+ (optional but recommended)

### Quick Start with kubectl

```bash
# 1. Create namespace
kubectl create namespace ai-pdf-scholar

# 2. Apply configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 3. Verify deployment
kubectl get pods -n ai-pdf-scholar
kubectl logs -f deployment/ai-pdf-scholar -n ai-pdf-scholar
```

### Kubernetes Manifests

#### Deployment (`k8s/deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-pdf-scholar
  namespace: ai-pdf-scholar
  labels:
    app: ai-pdf-scholar
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-pdf-scholar
  template:
    metadata:
      labels:
        app: ai-pdf-scholar
    spec:
      containers:
      - name: app
        image: ai-pdf-scholar:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: gemini
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/system/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/system/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: ai-pdf-scholar-data
```

#### Service (`k8s/service.yaml`)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-pdf-scholar
  namespace: ai-pdf-scholar
spec:
  selector:
    app: ai-pdf-scholar
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

#### Ingress (`k8s/ingress.yaml`)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-pdf-scholar
  namespace: ai-pdf-scholar
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - scholar.yourdomain.com
    secretName: ai-pdf-scholar-tls
  rules:
  - host: scholar.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ai-pdf-scholar
            port:
              number: 80
```

### Scaling Considerations

```bash
# Horizontal Pod Autoscaler
kubectl autoscale deployment ai-pdf-scholar \
  --cpu-percent=70 \
  --min=3 \
  --max=10 \
  --namespace=ai-pdf-scholar

# Vertical Pod Autoscaler (if installed)
kubectl apply -f k8s/vpa.yaml
```

---

## Manual Deployment

### Server Requirements

- **OS**: Ubuntu 22.04 LTS, CentOS 8+, or equivalent
- **RAM**: 4GB minimum, 8GB recommended
- **CPU**: 2 cores minimum, 4 cores recommended
- **Storage**: 20GB SSD minimum
- **Network**: Public IP, ports 80/443 open

### Step-by-Step Installation

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev -y

# 3. Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 4. Install system dependencies
sudo apt install -y build-essential libffi-dev libssl-dev

# 5. Create application directory
sudo mkdir -p /opt/ai-pdf-scholar
sudo chown $USER:$USER /opt/ai-pdf-scholar
cd /opt/ai-pdf-scholar

# 6. Clone repository
git clone https://github.com/Jackela/ai_enhanced_pdf_scholar.git .

# 7. Setup Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-prod.txt

# 8. Build frontend
cd frontend
npm ci
npm run build
cd ..

# 9. Configure environment
cp .env.example .env
# Edit .env with production settings

# 10. Initialize database
python -c "from src.database import init_db; init_db()"

# 11. Create systemd service
sudo tee /etc/systemd/system/ai-pdf-scholar.service << 'EOF'
[Unit]
Description=AI Enhanced PDF Scholar
After=network.target

[Service]
Type=simple
User=pdf-scholar
Group=pdf-scholar
WorkingDirectory=/opt/ai-pdf-scholar
Environment=PATH=/opt/ai-pdf-scholar/venv/bin
Environment=PYTHONPATH=/opt/ai-pdf-scholar
Environment=ENVIRONMENT=production
ExecStart=/opt/ai-pdf-scholar/venv/bin/uvicorn web_main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 12. Start service
sudo systemctl daemon-reload
sudo systemctl enable ai-pdf-scholar
sudo systemctl start ai-pdf-scholar

# 13. Configure Nginx (optional but recommended)
sudo apt install nginx -y
sudo tee /etc/nginx/sites-available/ai-pdf-scholar << 'EOF'
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/documents/ {
        client_max_body_size 100M;
        proxy_pass http://localhost:8000;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/ai-pdf-scholar /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Cloud Platform Deployment

### AWS Deployment

#### Using ECS (Elastic Container Service)

```bash
# 1. Create ECR repository
aws ecr create-repository --repository-name ai-pdf-scholar

# 2. Build and push image
aws ecr get-login-password | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

docker build -t ai-pdf-scholar .
docker tag ai-pdf-scholar:latest $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ai-pdf-scholar:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ai-pdf-scholar:latest

# 3. Create ECS cluster and service using AWS Console or CloudFormation
```

#### Using Elastic Beanstalk

```bash
# 1. Install EB CLI
pip install awsebcli

# 2. Initialize application
eb init -p python-3.11 ai-pdf-scholar

# 3. Create environment
eb create ai-pdf-scholar-prod

# 4. Deploy
eb deploy
```

### Google Cloud Platform

#### Cloud Run

```bash
# 1. Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/ai-pdf-scholar

# 2. Deploy to Cloud Run
gcloud run deploy ai-pdf-scholar \
  --image gcr.io/PROJECT_ID/ai-pdf-scholar \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "ENVIRONMENT=production" \
  --set-env-vars "GOOGLE_API_KEY=your-key"
```

### Azure Deployment

#### Container Instances

```bash
# 1. Create resource group
az group create --name ai-pdf-scholar-rg --location eastus

# 2. Create container
az container create \
  --resource-group ai-pdf-scholar-rg \
  --name ai-pdf-scholar \
  --image your-registry/ai-pdf-scholar:latest \
  --dns-name-label ai-pdf-scholar \
  --ports 8000 \
  --environment-variables ENVIRONMENT=production
```

---

## Post-Deployment Configuration

### 1. Initial System Setup

```bash
# Initialize system (run once)
curl -X POST http://yourdomain.com/api/system/initialize

# Verify health
curl http://yourdomain.com/api/system/health
```

### 2. Configure API Keys

Navigate to Settings in the web UI or use the API:

```bash
# Test API key
curl -X POST http://yourdomain.com/api/settings/test-api-key \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-gemini-key"}'

# Save settings
curl -X POST http://yourdomain.com/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "gemini_api_key": "your-key",
    "rag_enabled": true,
    "auto_build_index": true
  }'
```

### 3. SSL/TLS Configuration

#### Using Let's Encrypt (Certbot)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal test
sudo certbot renew --dry-run
```

#### Using Cloudflare

1. Update DNS to point to Cloudflare
2. Enable "Full (Strict)" SSL mode
3. Configure origin certificates

---

## Monitoring and Maintenance

### Health Checks

```bash
# Basic health check
curl http://yourdomain.com/api/system/health

# Detailed health check
curl http://yourdomain.com/api/system/health/detailed

# Dependency health check
curl http://yourdomain.com/api/system/health/dependencies

# Performance metrics
curl http://yourdomain.com/api/system/health/performance
```

### Log Management

```bash
# View application logs
sudo journalctl -u ai-pdf-scholar -f

# View nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Backup Strategy

```bash
# Database backup
#!/bin/bash
BACKUP_DIR="/backups/ai-pdf-scholar"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup SQLite database
cp /opt/ai-pdf-scholar/data/library.db $BACKUP_DIR/library_$DATE.db

# Backup documents
rsync -av /opt/ai-pdf-scholar/data/documents/ $BACKUP_DIR/documents/

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
```

### Automated Maintenance

```bash
# Add to crontab
crontab -e

# Daily maintenance at 3 AM
0 3 * * * curl -X POST http://localhost:8000/api/system/maintenance

# Weekly cleanup
0 4 * * 0 curl -X POST http://localhost:8000/api/library/cleanup
```

---

## Troubleshooting

### Common Issues

#### 1. Application Won't Start

```bash
# Check logs
sudo journalctl -u ai-pdf-scholar -n 100 --no-pager

# Verify environment
cat /opt/ai-pdf-scholar/.env | grep -v PASSWORD

# Test manually
cd /opt/ai-pdf-scholar
source venv/bin/activate
python web_main.py --debug
```

#### 2. Database Connection Issues

```bash
# Test database connection
python -c "
from src.database.connection import DatabaseConnection
db = DatabaseConnection()
print(db.fetch_one('SELECT 1'))
"

# Check database permissions
ls -la /opt/ai-pdf-scholar/data/
```

#### 3. Out of Memory

```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Configure swap (if needed)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### 4. File Upload Failures

```bash
# Check disk space
df -h

# Verify upload directory permissions
ls -la /opt/ai-pdf-scholar/data/uploads/

# Check nginx client_max_body_size
grep client_max_body /etc/nginx/sites-enabled/*
```

### Performance Optimization

#### Database Optimization

```bash
# For SQLite
sqlite3 /opt/ai-pdf-scholar/data/library.db "VACUUM;"
sqlite3 /opt/ai-pdf-scholar/data/library.db "ANALYZE;"

# For PostgreSQL
psql -c "VACUUM ANALYZE;"
```

#### Cache Warming

```bash
# Trigger cache warming
curl -X POST http://localhost:8000/api/cache/warm \
  -H "Content-Type: application/json" \
  -d '{"priority_documents": [1, 2, 3]}'
```

---

## Security Checklist

- [ ] Change default SECRET_KEY
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Configure CORS origins properly
- [ ] Set up rate limiting
- [ ] Enable request logging
- [ ] Configure firewall rules
- [ ] Set up automated backups
- [ ] Enable audit logging
- [ ] Regular security updates
- [ ] Use secrets management for API keys

---

## Support

For deployment support:
- **Documentation**: [docs/README.md](./docs/README.md)
- **Issues**: [GitHub Issues](https://github.com/Jackela/ai_enhanced_pdf_scholar/issues)
- **API Reference**: [API_ENDPOINTS.md](./API_ENDPOINTS.md)

---

**Last Updated**: March 27, 2026  
**Version**: 2.1.0
