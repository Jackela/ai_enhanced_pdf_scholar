# AI Enhanced PDF Scholar - Monitoring Operations Guide

## Overview

This guide provides comprehensive instructions for operating the monitoring infrastructure for the AI Enhanced PDF Scholar application. The monitoring stack includes Prometheus, Grafana, AlertManager, and the ELK Stack (Elasticsearch, Logstash, Kibana, Filebeat).

## Architecture Overview

```mermaid
graph TB
    App[AI PDF Scholar Backend] -->|Metrics| Prometheus[Prometheus]
    App -->|Logs| Filebeat[Filebeat]

    Filebeat -->|Logs| Logstash[Logstash]
    Logstash -->|Processed Logs| Elasticsearch[Elasticsearch]

    Prometheus -->|Alerts| AlertManager[AlertManager]
    AlertManager -->|Notifications| Slack[Slack]
    AlertManager -->|Notifications| Email[Email]
    AlertManager -->|Notifications| PagerDuty[PagerDuty]

    Prometheus -->|Data| Grafana[Grafana]
    Elasticsearch -->|Log Data| Kibana[Kibana]

    Users[Operations Team] -->|Dashboards| Grafana
    Users -->|Log Analysis| Kibana
```

## Components

### 1. Prometheus - Metrics Collection
- **Purpose**: Time-series metrics collection and storage
- **Port**: 9090
- **Data Retention**: 90 days
- **Storage**: 100Gi with fast-SSD storage class
- **High Availability**: 2 replicas with sharding

### 2. Grafana - Visualization
- **Purpose**: Metrics visualization and dashboards
- **Port**: 3000
- **Default Credentials**: admin / (set via secret)
- **Dashboards**: Application Performance, Infrastructure Health, Business Metrics

### 3. AlertManager - Alert Routing
- **Purpose**: Alert routing and notification management
- **Port**: 9093
- **High Availability**: 2 replicas with clustering
- **Channels**: Email, Slack, PagerDuty, Teams, Webhook

### 4. ELK Stack - Log Management
- **Elasticsearch**: Log storage and indexing (Port: 9200)
- **Logstash**: Log processing and transformation (Port: 5044, 8080)
- **Kibana**: Log visualization and analysis (Port: 5601)
- **Filebeat**: Log collection from all pods

## Deployment Instructions

### Prerequisites
1. Kubernetes cluster with monitoring namespace
2. StorageClass `fast-ssd` configured
3. Required secrets created

### 1. Create Secrets
```bash
# Create monitoring namespace
kubectl create namespace ai-pdf-scholar

# Create Grafana credentials
kubectl create secret generic grafana-credentials \
  --from-literal=admin-password='your-secure-password' \
  --from-literal=secret-key='your-secret-key' \
  -n ai-pdf-scholar

# Create AlertManager secrets (optional)
kubectl create secret generic alertmanager-secrets \
  --from-literal=slack-api-url='https://hooks.slack.com/your-webhook' \
  --from-literal=pagerduty-routing-key='your-pagerduty-key' \
  -n ai-pdf-scholar

# Create PostgreSQL exporter credentials
kubectl create secret generic postgresql-credentials \
  --from-literal=postgres-exporter-url='postgresql://user:password@host:5432/dbname?sslmode=disable' \
  -n ai-pdf-scholar
```

### 2. Deploy Monitoring Stack
```bash
# Deploy in order
kubectl apply -f k8s/manifests/prometheus.yaml
kubectl apply -f k8s/manifests/alertmanager.yaml
kubectl apply -f k8s/manifests/monitoring.yaml  # ELK Stack
kubectl apply -f k8s/manifests/filebeat.yaml
kubectl apply -f k8s/manifests/grafana.yaml

# Verify deployments
kubectl get pods -n ai-pdf-scholar
kubectl get services -n ai-pdf-scholar
```

### 3. Access Dashboards
```bash
# Grafana (port-forward)
kubectl port-forward svc/grafana 3000:3000 -n ai-pdf-scholar

# Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n ai-pdf-scholar

# Kibana
kubectl port-forward svc/kibana 5601:5601 -n ai-pdf-scholar

# AlertManager
kubectl port-forward svc/alertmanager 9093:9093 -n ai-pdf-scholar
```

## Monitoring Operations

### 1. Daily Operations Checklist

#### Morning Checks (5 minutes)
- [ ] Check Grafana dashboards for overnight alerts
- [ ] Verify all monitoring services are healthy
- [ ] Review error logs in Kibana for patterns
- [ ] Check AlertManager for pending alerts

#### Weekly Maintenance (30 minutes)
- [ ] Review disk usage for monitoring components
- [ ] Update alert thresholds based on trends
- [ ] Clean up old log indices
- [ ] Test alert notification channels

#### Monthly Tasks (1 hour)
- [ ] Review monitoring metrics and optimize
- [ ] Update dashboard configurations
- [ ] Analyze long-term trends
- [ ] Plan capacity adjustments

### 2. Key Metrics to Monitor

#### Application Health
- **HTTP Request Rate**: Target <100 req/sec normally
- **Response Time P95**: Target <2 seconds
- **Error Rate**: Target <1%
- **RAG Query Performance**: Target <10 seconds P95

#### Infrastructure Health
- **CPU Usage**: Alert at >85%
- **Memory Usage**: Alert at >90%
- **Disk Space**: Alert at <10% free
- **Pod Restart Count**: Alert on frequent restarts

#### Business Metrics
- **Document Upload Success Rate**: Target >95%
- **User Activity**: Track daily/monthly trends
- **Feature Usage**: Monitor adoption rates
- **Cache Hit Rate**: Target >80%

### 3. Alert Response Procedures

#### Critical Alerts (Immediate Response - <5 minutes)
1. **Service Down**
   - Check pod status: `kubectl get pods -n ai-pdf-scholar`
   - Review pod logs: `kubectl logs <pod-name> -n ai-pdf-scholar`
   - Restart if necessary: `kubectl delete pod <pod-name> -n ai-pdf-scholar`

2. **High Error Rate**
   - Check recent deployments
   - Review error logs in Kibana
   - Rollback if deployment-related
   - Scale resources if capacity-related

3. **Memory/CPU Critical**
   - Identify high-usage pods
   - Check for memory leaks in logs
   - Scale horizontally if possible
   - Plan vertical scaling

#### Warning Alerts (Response within 30 minutes)
1. **High Latency**
   - Analyze slow queries in logs
   - Check database performance metrics
   - Review cache hit rates
   - Consider scaling or optimization

2. **Security Events**
   - Review failed login attempts
   - Check for suspicious IP addresses
   - Verify rate limiting effectiveness
   - Update security rules if needed

### 4. Troubleshooting Common Issues

#### Metrics Not Appearing
1. Check Prometheus targets: `http://prometheus:9090/targets`
2. Verify service annotations for scraping
3. Check network policies and firewall rules
4. Restart Prometheus if configuration changed

#### Logs Not Flowing
1. Check Filebeat status on all nodes
2. Verify Logstash processing pipeline
3. Check Elasticsearch cluster health
4. Review log parsing rules in Logstash

#### Alerts Not Firing
1. Check AlertManager configuration
2. Verify alert rules syntax in Prometheus
3. Test notification channels manually
4. Check alert rule evaluation intervals

#### Dashboard Issues
1. Verify Grafana datasource connections
2. Check dashboard query syntax
3. Review time range and refresh settings
4. Clear browser cache and reload

### 5. Performance Optimization

#### Prometheus Optimization
- Adjust scrape intervals based on needs
- Use recording rules for expensive queries
- Monitor memory usage and tune retention
- Consider federation for multiple clusters

#### Elasticsearch Optimization
- Implement index lifecycle management (ILM)
- Optimize shard size and allocation
- Use index templates for consistent mapping
- Monitor cluster health and performance

#### Log Management
- Filter unnecessary logs at Filebeat level
- Use structured logging in applications
- Implement log sampling for high-volume services
- Archive old logs to cold storage

### 6. Backup and Disaster Recovery

#### Data Backup
```bash
# Prometheus data backup
kubectl exec -n ai-pdf-scholar prometheus-0 -- tar czf /prometheus/backup-$(date +%Y%m%d).tar.gz /prometheus/data

# Grafana dashboard backup
kubectl exec -n ai-pdf-scholar grafana-xxx -- sqlite3 /var/lib/grafana/grafana.db .dump > grafana-backup-$(date +%Y%m%d).sql

# Elasticsearch snapshots
curl -X PUT "elasticsearch:9200/_snapshot/backup_repo/snapshot_$(date +%Y%m%d)"
```

#### Recovery Procedures
1. **Prometheus Recovery**
   - Restore data from backup
   - Verify metric retention periods
   - Restart pods to reload configuration

2. **Grafana Recovery**
   - Restore dashboard database
   - Reimport dashboard configurations
   - Verify datasource connections

3. **Elasticsearch Recovery**
   - Restore from snapshot repository
   - Verify index patterns and mappings
   - Restart Kibana to refresh

### 7. Security Considerations

#### Access Control
- Use RBAC for Kubernetes monitoring components
- Implement proper authentication for Grafana
- Secure AlertManager notification channels
- Regular credential rotation

#### Data Protection
- Encrypt sensitive data in logs
- Use TLS for all monitoring communications
- Implement network policies for pod-to-pod traffic
- Regular security audits of monitoring stack

#### Log Sanitization
- Remove PII from logs before processing
- Implement log masking for sensitive data
- Monitor for credential leaks in logs
- Regular compliance checks

### 8. Scaling Guidelines

#### Horizontal Scaling
- **Prometheus**: Use federation for multiple clusters
- **AlertManager**: Scale replicas for high availability
- **Elasticsearch**: Add data nodes for storage/performance
- **Filebeat**: Automatically scales with node count

#### Vertical Scaling
- **Prometheus**: Increase memory for larger retention
- **Grafana**: Scale CPU for complex dashboards
- **Logstash**: Scale memory for heavy processing
- **Kibana**: Scale for concurrent users

### 9. Integration Points

#### CI/CD Pipeline Integration
- Monitor deployment success rates
- Alert on deployment failures
- Track deployment performance impact
- Automated rollback triggers

#### Application Integration
- Custom metric endpoints
- Structured logging implementation
- Health check endpoints
- Distributed tracing integration

#### External Systems
- Cloud provider metrics integration
- Third-party service monitoring
- External API performance tracking
- Cost monitoring integration

## Emergency Contacts

### Escalation Matrix
1. **Level 1**: On-call Engineer (Immediate)
2. **Level 2**: Senior Engineering (30 minutes)
3. **Level 3**: Engineering Manager (1 hour)
4. **Level 4**: VP Engineering (2 hours)

### Communication Channels
- **Slack**: #ai-pdf-scholar-alerts
- **Email**: alerts@ai-pdf-scholar.com
- **Phone**: Emergency on-call rotation
- **Documentation**: Internal wiki for procedures

## Appendix

### A. Alert Rule Examples
See `monitoring/alerts.yml` for comprehensive alert rules.

### B. Dashboard Queries
See `monitoring/grafana/dashboards/` for dashboard configurations.

### C. Runbook Links
- Service Down: https://runbook.ai-pdf-scholar.com/service-down
- Performance Issues: https://runbook.ai-pdf-scholar.com/performance
- Security Incidents: https://runbook.ai-pdf-scholar.com/security

### D. Useful Commands
```bash
# Check monitoring stack health
kubectl get pods -n ai-pdf-scholar -l app.kubernetes.io/component=monitoring

# View recent alerts
curl -s http://alertmanager:9093/api/v1/alerts

# Check Prometheus configuration
curl -s http://prometheus:9090/api/v1/status/config

# View Elasticsearch cluster health
curl -s http://elasticsearch:9200/_cluster/health?pretty
```

---

**Document Version**: 1.0
**Last Updated**: 2025-01-19
**Next Review**: 2025-04-19
**Owner**: DevOps Team
**Approved By**: Engineering Manager