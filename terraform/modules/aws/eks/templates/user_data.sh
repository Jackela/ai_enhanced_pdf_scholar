#!/bin/bash

# EKS Node Group User Data Script
# This script configures EKS worker nodes with security hardening

set -o xtrace

# Update system
yum update -y

# Configure the kubelet
# The /etc/kubernetes/kubelet/kubelet-config.json file is created by the EKS-optimized AMI
# We can modify it to add additional configuration

B64_CLUSTER_CA="${ca_data}"
API_SERVER_URL="${endpoint}"
K8S_CLUSTER_DNS_IP="172.20.0.10"

# Get instance metadata
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)

# Bootstrap the node
/etc/eks/bootstrap.sh "${cluster_name}" \
  --b64-cluster-ca "$B64_CLUSTER_CA" \
  --apiserver-endpoint "$API_SERVER_URL" \
  --dns-cluster-ip "$K8S_CLUSTER_DNS_IP" \
  --container-runtime containerd \
  --kubelet-extra-args "--node-labels=node.kubernetes.io/instance-type=$(curl -s http://169.254.169.254/latest/meta-data/instance-type),topology.kubernetes.io/region=$REGION,topology.kubernetes.io/zone=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)"

# Install additional packages for monitoring and security
yum install -y amazon-cloudwatch-agent
yum install -y awscli
yum install -y jq

# Configure CloudWatch agent for EKS
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'
{
  "agent": {
    "region": "$(curl -s http://169.254.169.254/latest/meta-data/placement/region)",
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
        "metrics_collection_interval": 60,
        "totalcpu": false
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
      "ClusterName": "${cluster_name}",
      "NodeGroup": "$(curl -s http://169.254.169.254/latest/meta-data/tags/instance/kubernetes.io/cluster/${cluster_name})",
      "InstanceId": "$(curl -s http://169.254.169.254/latest/meta-data/instance-id)"
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/messages",
            "log_group_name": "/aws/eks/${cluster_name}/node-system-logs",
            "log_stream_name": "{instance_id}/messages"
          },
          {
            "file_path": "/var/log/dmesg",
            "log_group_name": "/aws/eks/${cluster_name}/node-system-logs",
            "log_stream_name": "{instance_id}/dmesg"
          },
          {
            "file_path": "/var/log/audit/audit.log",
            "log_group_name": "/aws/eks/${cluster_name}/node-audit-logs",
            "log_stream_name": "{instance_id}/audit"
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
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
  -s

# Security hardening
# Disable unnecessary services
systemctl disable rpcbind
systemctl stop rpcbind

# Set kernel parameters for security
cat >> /etc/sysctl.conf << 'EOF'

# Security hardening for EKS nodes
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
kernel.dmesg_restrict = 1
EOF

sysctl -p

# Configure log rotation for container logs
cat > /etc/logrotate.d/docker-container << 'EOF'
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

# Set up node monitoring script
cat > /usr/local/bin/node-health-check.sh << 'EOF'
#!/bin/bash
# Node health check script

LOG_FILE="/var/log/node-health.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Check disk space
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "$TIMESTAMP - WARNING: Disk usage is at $DISK_USAGE%" >> $LOG_FILE
fi

# Check memory usage
MEM_USAGE=$(free | awk 'NR==2{printf "%.2f", $3*100/$2 }')
if (( $(echo "$MEM_USAGE > 85" | bc -l) )); then
    echo "$TIMESTAMP - WARNING: Memory usage is at $MEM_USAGE%" >> $LOG_FILE
fi

# Check if kubelet is running
if ! systemctl is-active --quiet kubelet; then
    echo "$TIMESTAMP - ERROR: kubelet is not running" >> $LOG_FILE
    systemctl restart kubelet
fi

# Check if docker/containerd is running
if ! systemctl is-active --quiet containerd; then
    echo "$TIMESTAMP - ERROR: containerd is not running" >> $LOG_FILE
    systemctl restart containerd
fi
EOF

chmod +x /usr/local/bin/node-health-check.sh

# Add cron job for health checks
echo "*/5 * * * * /usr/local/bin/node-health-check.sh" | crontab -

# Configure containerd for EKS
cat > /etc/containerd/config.toml << 'EOF'
version = 2

[plugins."io.containerd.grpc.v1.cri"]
  sandbox_image = "602401143452.dkr.ecr.us-west-2.amazonaws.com/eks/pause:3.5"

[plugins."io.containerd.grpc.v1.cri".containerd]
  default_runtime_name = "runc"

[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
  runtime_type = "io.containerd.runc.v2"

[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
  SystemdCgroup = true
EOF

systemctl restart containerd

# Signal completion
/opt/aws/bin/cfn-signal -e $? --stack ${AWS::StackName} --resource NodeGroup --region ${AWS::Region}

echo "Node setup completed successfully" >> /var/log/user-data.log