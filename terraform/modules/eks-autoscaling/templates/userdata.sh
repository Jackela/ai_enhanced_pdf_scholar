#!/bin/bash

# ============================================================================
# EKS Node User Data Script
# Optimized bootstrap script for AI PDF Scholar EKS nodes
# Includes cost optimization and performance monitoring setup
# ============================================================================

set -o xtrace

# Variables passed from Terraform
CLUSTER_NAME=${cluster_name}
BOOTSTRAP_ARGS="${bootstrap_args}"
CLUSTER_ENDPOINT=${cluster_endpoint}
CLUSTER_CA_CERTIFICATE=${cluster_ca}

# System optimization
echo "Applying system optimizations..."

# Increase file descriptor limits for high-throughput workloads
cat >> /etc/security/limits.conf << EOF
* soft nofile 65536
* hard nofile 65536
* soft nproc 65536
* hard nproc 65536
EOF

# Kernel parameter tuning for networking and memory
cat >> /etc/sysctl.d/99-kubernetes.conf << EOF
# Network optimizations
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 12582912 16777216
net.ipv4.tcp_wmem = 4096 12582912 16777216
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_congestion_control = bbr

# Memory management
vm.swappiness = 1
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
vm.vfs_cache_pressure = 50

# File system
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288
EOF

sysctl -p /etc/sysctl.d/99-kubernetes.conf

# Install additional packages for monitoring and optimization
yum update -y
yum install -y \
    htop \
    iotop \
    nload \
    jq \
    aws-cli \
    amazon-cloudwatch-agent \
    collectd \
    node_exporter

# Install Docker (if needed) with optimized configuration
if ! command -v docker &> /dev/null; then
    yum install -y docker
    systemctl enable docker
    
    # Docker daemon optimization
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << EOF
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ],
    "exec-opts": ["native.cgroupdriver=systemd"],
    "data-root": "/var/lib/docker",
    "live-restore": true
}
EOF
    
    systemctl start docker
fi

# Configure containerd optimizations
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml

# Optimize containerd configuration for AI workloads
cat >> /etc/containerd/config.toml << EOF

# AI/ML workload optimizations
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
  SystemdCgroup = true

[plugins."io.containerd.grpc.v1.cri"]
  sandbox_image = "602401143452.dkr.ecr.us-west-2.amazonaws.com/eks/pause:3.5"
  max_concurrent_downloads = 10
  
[plugins."io.containerd.grpc.v1.cri".registry]
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
      endpoint = ["https://registry-1.docker.io"]
      
[plugins."io.containerd.grpc.v1.cri".containerd]
  snapshotter = "overlayfs"
  default_runtime_name = "runc"
  
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes]
  [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
    runtime_type = "io.containerd.runc.v2"
EOF

systemctl restart containerd
systemctl enable containerd

# Install and configure Node Exporter for Prometheus monitoring
cat > /etc/systemd/system/node_exporter.service << EOF
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=nobody
Group=nobody
Type=simple
ExecStart=/usr/local/bin/node_exporter \\
    --web.listen-address=:9100 \\
    --collector.filesystem.ignored-mount-points="^/(dev|proc|sys|var/lib/docker/.+)($|/)" \\
    --collector.filesystem.ignored-fs-types="^(autofs|binfmt_misc|cgroup|configfs|debugfs|devpts|devtmpfs|fusectl|hugetlbfs|mqueue|overlay|proc|procfs|pstore|rpc_pipefs|securityfs|sysfs|tracefs)$"

[Install]
WantedBy=multi-user.target
EOF

# Download and install node_exporter
cd /tmp
curl -LO https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
tar -xzf node_exporter-1.6.1.linux-amd64.tar.gz
cp node_exporter-1.6.1.linux-amd64/node_exporter /usr/local/bin/
chown nobody:nobody /usr/local/bin/node_exporter

systemctl daemon-reload
systemctl enable node_exporter
systemctl start node_exporter

# Configure CloudWatch agent for additional metrics
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << EOF
{
    "agent": {
        "metrics_collection_interval": 60,
        "run_as_user": "cwagent"
    },
    "metrics": {
        "namespace": "EKS/NodeMetrics",
        "metrics_collected": {
            "cpu": {
                "measurement": [
                    "cpu_usage_idle",
                    "cpu_usage_iowait",
                    "cpu_usage_user",
                    "cpu_usage_system"
                ],
                "metrics_collection_interval": 60
            },
            "disk": {
                "measurement": [
                    "used_percent"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "*"
                ]
            },
            "diskio": {
                "measurement": [
                    "io_time",
                    "read_bytes",
                    "write_bytes",
                    "reads",
                    "writes"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "*"
                ]
            },
            "mem": {
                "measurement": [
                    "mem_used_percent"
                ],
                "metrics_collection_interval": 60
            },
            "netstat": {
                "measurement": [
                    "tcp_established",
                    "tcp_time_wait"
                ],
                "metrics_collection_interval": 60
            },
            "swap": {
                "measurement": [
                    "swap_used_percent"
                ],
                "metrics_collection_interval": 60
            }
        },
        "append_dimensions": {
            "AutoScalingGroupName": "$${aws:AutoScalingGroupName}",
            "InstanceId": "$${aws:InstanceId}",
            "InstanceType": "$${aws:InstanceType}",
            "ClusterName": "$CLUSTER_NAME"
        }
    },
    "logs": {
        "logs_collected": {
            "files": {
                "collect_list": [
                    {
                        "file_path": "/var/log/messages",
                        "log_group_name": "/aws/eks/$CLUSTER_NAME/system",
                        "log_stream_name": "{instance_id}/messages"
                    },
                    {
                        "file_path": "/var/log/dmesg",
                        "log_group_name": "/aws/eks/$CLUSTER_NAME/system",
                        "log_stream_name": "{instance_id}/dmesg"
                    }
                ]
            }
        }
    }
}
EOF

# Start CloudWatch agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

# Configure log rotation for container logs
cat > /etc/logrotate.d/docker-containers << EOF
/var/lib/docker/containers/*/*.log {
    rotate 5
    daily
    compress
    size 10M
    missingok
    delaycompress
    copytruncate
}
EOF

# Set up automatic security updates
echo "unattended-upgrades unattended-upgrades/enable_auto_updates boolean true" | debconf-set-selections
yum install -y yum-cron
systemctl enable yum-cron
systemctl start yum-cron

# Configure yum-cron for security updates only
sed -i 's/update_cmd = default/update_cmd = security/' /etc/yum/yum-cron.conf
sed -i 's/apply_updates = no/apply_updates = yes/' /etc/yum/yum-cron.conf

# Create scripts for cost monitoring
cat > /usr/local/bin/cost-monitor.sh << 'EOF'
#!/bin/bash
# Simple cost monitoring script

INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
INSTANCE_TYPE=$(curl -s http://169.254.169.254/latest/meta-data/instance-type)
AVAILABILITY_ZONE=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)
REGION=${AVAILABILITY_ZONE%?}

# Log instance utilization metrics
echo "$(date): Instance $INSTANCE_ID ($INSTANCE_TYPE) utilization check" >> /var/log/cost-monitor.log

# CPU utilization
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
echo "  CPU Usage: ${CPU_USAGE}%" >> /var/log/cost-monitor.log

# Memory utilization
MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.2f", $3/$2 * 100.0)}')
echo "  Memory Usage: ${MEMORY_USAGE}%" >> /var/log/cost-monitor.log

# Disk utilization
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}')
echo "  Disk Usage: ${DISK_USAGE}" >> /var/log/cost-monitor.log

# Network connections
CONNECTIONS=$(netstat -tn | grep ESTABLISHED | wc -l)
echo "  Active Connections: ${CONNECTIONS}" >> /var/log/cost-monitor.log

# Send metrics to CloudWatch (optional)
aws cloudwatch put-metric-data \
    --namespace "EKS/CostOptimization" \
    --metric-data MetricName=CPUUtilization,Value=$CPU_USAGE,Unit=Percent,Dimensions=InstanceId=$INSTANCE_ID,InstanceType=$INSTANCE_TYPE \
    --region $REGION

aws cloudwatch put-metric-data \
    --namespace "EKS/CostOptimization" \
    --metric-data MetricName=MemoryUtilization,Value=$MEMORY_USAGE,Unit=Percent,Dimensions=InstanceId=$INSTANCE_ID,InstanceType=$INSTANCE_TYPE \
    --region $REGION
EOF

chmod +x /usr/local/bin/cost-monitor.sh

# Set up cron job for cost monitoring
echo "*/5 * * * * /usr/local/bin/cost-monitor.sh" | crontab -

# Create spot instance interruption handler
cat > /usr/local/bin/spot-interruption-handler.sh << 'EOF'
#!/bin/bash
# Spot instance interruption handler

INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

while true; do
    # Check for spot interruption notice
    HTTP_CODE=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s -w "%{http_code}" -o /dev/null http://169.254.169.254/latest/meta-data/spot/instance-action)
    
    if [[ "$HTTP_CODE" -eq 200 ]]; then
        echo "$(date): Spot interruption notice received for instance $INSTANCE_ID" >> /var/log/spot-interruption.log
        
        # Gracefully drain the node
        kubectl drain $(hostname) --ignore-daemonsets --delete-emptydir-data --force --grace-period=120
        
        # Wait a bit for graceful shutdown
        sleep 30
        
        echo "$(date): Node drained successfully" >> /var/log/spot-interruption.log
        break
    fi
    
    sleep 5
done
EOF

chmod +x /usr/local/bin/spot-interruption-handler.sh

# Create systemd service for spot interruption handler
cat > /etc/systemd/system/spot-interruption-handler.service << EOF
[Unit]
Description=Spot Instance Interruption Handler
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/spot-interruption-handler.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable spot-interruption-handler
systemctl start spot-interruption-handler

# Install AWS Node Termination Handler (for spot instances)
if [[ "$BOOTSTRAP_ARGS" == *"spot"* ]]; then
    curl -Lo /tmp/node-termination-handler.tar.gz \
        https://github.com/aws/aws-node-termination-handler/releases/download/v1.21.0/linux-amd64.tar.gz
    
    tar -xzf /tmp/node-termination-handler.tar.gz -C /tmp/
    mv /tmp/node-termination-handler /usr/local/bin/
    chmod +x /usr/local/bin/node-termination-handler
    
    # Create systemd service
    cat > /etc/systemd/system/aws-node-termination-handler.service << EOF
[Unit]
Description=AWS Node Termination Handler
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/node-termination-handler \
    --node-name=\$(hostname) \
    --metadata-tries=3 \
    --cordon-only=false \
    --taint-node=false \
    --delete-local-data=true \
    --ignore-daemon-sets=true \
    --pod-termination-grace-period=120 \
    --node-termination-grace-period=120
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable aws-node-termination-handler
    systemctl start aws-node-termination-handler
fi

# Pre-pull commonly used images to reduce startup time
echo "Pre-pulling common container images..."
docker pull public.ecr.aws/eks-distro/kubernetes/pause:3.2
docker pull amazon/aws-cli:latest
docker pull prom/node-exporter:latest

# Setup cleanup script for old container images
cat > /usr/local/bin/cleanup-docker.sh << 'EOF'
#!/bin/bash
# Cleanup old Docker images and containers to save space

echo "$(date): Starting Docker cleanup" >> /var/log/docker-cleanup.log

# Remove stopped containers older than 24 hours
docker container prune -f --filter "until=24h" >> /var/log/docker-cleanup.log 2>&1

# Remove unused images older than 24 hours
docker image prune -a -f --filter "until=24h" >> /var/log/docker-cleanup.log 2>&1

# Remove unused volumes
docker volume prune -f >> /var/log/docker-cleanup.log 2>&1

# Remove unused networks
docker network prune -f >> /var/log/docker-cleanup.log 2>&1

echo "$(date): Docker cleanup completed" >> /var/log/docker-cleanup.log
EOF

chmod +x /usr/local/bin/cleanup-docker.sh

# Schedule daily cleanup
echo "0 2 * * * /usr/local/bin/cleanup-docker.sh" >> /var/spool/cron/root

# Optimize EBS volume performance
echo deadline > /sys/block/nvme0n1/queue/scheduler
echo 1024 > /sys/block/nvme0n1/queue/nr_requests

# Make EBS optimizations persistent
echo 'ACTION=="add|change", KERNEL=="nvme*", ATTR{queue/scheduler}="deadline"' > /etc/udev/rules.d/99-nvme-scheduler.rules
echo 'ACTION=="add|change", KERNEL=="nvme*", ATTR{queue/nr_requests}="1024"' >> /etc/udev/rules.d/99-nvme-scheduler.rules

# Configure kubelet with optimized settings
mkdir -p /etc/kubernetes/kubelet
cat > /etc/kubernetes/kubelet/kubelet-config.json << EOF
{
  "kind": "KubeletConfiguration",
  "apiVersion": "kubelet.config.k8s.io/v1beta1",
  "address": "0.0.0.0",
  "port": 10250,
  "readOnlyPort": 0,
  "cgroupDriver": "systemd",
  "hairpinMode": "hairpin-veth",
  "serializeImagePulls": false,
  "maxPods": 110,
  "featureGates": {
    "RotateKubeletServerCertificate": true,
    "CSIMigration": true
  },
  "serverTLSBootstrap": true,
  "authentication": {
    "x509": {},
    "webhook": {
      "enabled": true,
      "cacheTTL": "30s"
    },
    "anonymous": {
      "enabled": false
    }
  },
  "authorization": {
    "mode": "Webhook",
    "webhook": {
      "cacheAuthorizedTTL": "300s",
      "cacheUnauthorizedTTL": "30s"
    }
  },
  "registryPullQPS": 10,
  "registryBurst": 20,
  "eventRecordQPS": 50,
  "eventBurst": 100,
  "enableDebuggingHandlers": true,
  "healthzPort": 10248,
  "healthzBindAddress": "127.0.0.1",
  "oomScoreAdj": -999,
  "clusterDNS": ["172.20.0.10"],
  "clusterDomain": "cluster.local",
  "streamingConnectionIdleTimeout": "4h",
  "nodeStatusUpdateFrequency": "10s",
  "imageMinimumGCAge": "2m",
  "imageGCHighThresholdPercent": 85,
  "imageGCLowThresholdPercent": 80,
  "volumeStatsAggPeriod": "1m",
  "systemReserved": {
    "cpu": "100m",
    "memory": "100Mi",
    "ephemeral-storage": "1Gi"
  },
  "kubeReserved": {
    "cpu": "100m",
    "memory": "100Mi",
    "ephemeral-storage": "1Gi"
  },
  "evictionHard": {
    "memory.available": "100Mi",
    "nodefs.available": "10%",
    "nodefs.inodesFree": "5%",
    "imagefs.available": "15%"
  },
  "evictionSoft": {
    "memory.available": "200Mi",
    "nodefs.available": "15%",
    "nodefs.inodesFree": "10%",
    "imagefs.available": "20%"
  },
  "evictionSoftGracePeriod": {
    "memory.available": "1m30s",
    "nodefs.available": "2m",
    "nodefs.inodesFree": "2m",
    "imagefs.available": "2m"
  }
}
EOF

# Final step: Bootstrap the EKS node
/etc/eks/bootstrap.sh $CLUSTER_NAME $BOOTSTRAP_ARGS

echo "Node bootstrap completed successfully at $(date)" >> /var/log/user-data.log