# ============================================================================
# EKS Auto-Scaling Module Outputs
# Output values for integration with other infrastructure components
# ============================================================================

# Node Groups
output "cost_optimized_node_group_arn" {
  description = "ARN of the cost-optimized node group"
  value       = aws_eks_node_group.cost_optimized.arn
}

output "cost_optimized_node_group_id" {
  description = "ID of the cost-optimized node group"
  value       = aws_eks_node_group.cost_optimized.id
}

output "performance_optimized_node_group_arn" {
  description = "ARN of the performance-optimized node group"
  value       = aws_eks_node_group.performance_optimized.arn
}

output "performance_optimized_node_group_id" {
  description = "ID of the performance-optimized node group"
  value       = aws_eks_node_group.performance_optimized.id
}

# Launch Templates
output "cost_optimized_launch_template_id" {
  description = "ID of the cost-optimized launch template"
  value       = aws_launch_template.cost_optimized.id
}

output "cost_optimized_launch_template_version" {
  description = "Latest version of the cost-optimized launch template"
  value       = aws_launch_template.cost_optimized.latest_version
}

output "performance_optimized_launch_template_id" {
  description = "ID of the performance-optimized launch template"
  value       = aws_launch_template.performance_optimized.id
}

output "performance_optimized_launch_template_version" {
  description = "Latest version of the performance-optimized launch template"
  value       = aws_launch_template.performance_optimized.latest_version
}

# Auto Scaling Groups
output "cost_optimized_asg_name" {
  description = "Name of the cost-optimized auto scaling group"
  value       = aws_eks_node_group.cost_optimized.resources[0].autoscaling_groups[0].name
}

output "performance_optimized_asg_name" {
  description = "Name of the performance-optimized auto scaling group"
  value       = aws_eks_node_group.performance_optimized.resources[0].autoscaling_groups[0].name
}

# IAM Roles
output "cluster_autoscaler_role_arn" {
  description = "ARN of the Cluster Autoscaler IAM role"
  value       = aws_iam_role.cluster_autoscaler.arn
}

output "cluster_autoscaler_role_name" {
  description = "Name of the Cluster Autoscaler IAM role"
  value       = aws_iam_role.cluster_autoscaler.name
}

# Service Accounts
output "cluster_autoscaler_service_account_name" {
  description = "Name of the Cluster Autoscaler service account"
  value       = kubernetes_service_account.cluster_autoscaler.metadata[0].name
}

# Scaling Configuration
output "scaling_configuration" {
  description = "Current scaling configuration for monitoring and optimization"
  value = {
    cost_optimized = {
      min_size     = aws_eks_node_group.cost_optimized.scaling_config[0].min_size
      max_size     = aws_eks_node_group.cost_optimized.scaling_config[0].max_size
      desired_size = aws_eks_node_group.cost_optimized.scaling_config[0].desired_size
      capacity_type = aws_eks_node_group.cost_optimized.capacity_type
      instance_types = aws_eks_node_group.cost_optimized.instance_types
    }
    performance_optimized = {
      min_size     = aws_eks_node_group.performance_optimized.scaling_config[0].min_size
      max_size     = aws_eks_node_group.performance_optimized.scaling_config[0].max_size
      desired_size = aws_eks_node_group.performance_optimized.scaling_config[0].desired_size
      capacity_type = aws_eks_node_group.performance_optimized.capacity_type
      instance_types = aws_eks_node_group.performance_optimized.instance_types
    }
  }
}

# Auto Scaling Policies
output "scale_up_policy_arn" {
  description = "ARN of the scale up policy"
  value       = aws_autoscaling_policy.scale_up_policy.arn
}

output "scale_down_policy_arn" {
  description = "ARN of the scale down policy"
  value       = aws_autoscaling_policy.scale_down_policy.arn
}

# CloudWatch Alarms
output "cpu_high_alarm_arn" {
  description = "ARN of the CPU high utilization alarm"
  value       = aws_cloudwatch_metric_alarm.cpu_high.arn
}

output "cpu_low_alarm_arn" {
  description = "ARN of the CPU low utilization alarm"
  value       = aws_cloudwatch_metric_alarm.cpu_low.arn
}

# CloudWatch Log Group
output "cluster_autoscaler_log_group_name" {
  description = "Name of the Cluster Autoscaler CloudWatch log group"
  value       = aws_cloudwatch_log_group.cluster_autoscaler.name
}

output "cluster_autoscaler_log_group_arn" {
  description = "ARN of the Cluster Autoscaler CloudWatch log group"
  value       = aws_cloudwatch_log_group.cluster_autoscaler.arn
}

# Helm Releases
output "cluster_autoscaler_helm_status" {
  description = "Status of the Cluster Autoscaler Helm release"
  value       = helm_release.cluster_autoscaler.status
}

output "aws_load_balancer_controller_helm_status" {
  description = "Status of the AWS Load Balancer Controller Helm release"
  value       = helm_release.aws_load_balancer_controller.status
}

output "karpenter_helm_status" {
  description = "Status of the Karpenter Helm release (if enabled)"
  value       = var.enable_karpenter ? helm_release.karpenter[0].status : null
}

# Cost Optimization Metrics
output "cost_optimization_summary" {
  description = "Summary of cost optimization features enabled"
  value = {
    spot_instances_enabled = true
    mixed_instance_types  = true
    auto_scaling_enabled  = true
    cost_optimized_node_group = {
      min_size = aws_eks_node_group.cost_optimized.scaling_config[0].min_size
      max_size = aws_eks_node_group.cost_optimized.scaling_config[0].max_size
      spot_percentage = var.spot_instance_percentage
    }
    performance_node_group = {
      min_size = aws_eks_node_group.performance_optimized.scaling_config[0].min_size
      max_size = aws_eks_node_group.performance_optimized.scaling_config[0].max_size
      on_demand_only = true
    }
    karpenter_enabled = var.enable_karpenter
    load_balancer_controller_enabled = true
  }
}

# Node Selector Information
output "node_selectors" {
  description = "Node selectors for workload placement"
  value = {
    cost_optimized = {
      "node.kubernetes.io/lifecycle" = "spot"
      "cost-optimization" = "enabled"
    }
    performance_optimized = {
      "node.kubernetes.io/lifecycle" = "on-demand"
      "performance-optimization" = "enabled"
    }
  }
}

# Tolerations for Spot Instances
output "spot_tolerations" {
  description = "Tolerations needed for spot instances"
  value = [
    {
      key      = "node.kubernetes.io/lifecycle"
      operator = "Equal"
      value    = "spot"
      effect   = "NoSchedule"
    }
  ]
}

# Auto Scaling Recommendations
output "scaling_recommendations" {
  description = "Recommendations for optimal scaling configuration"
  value = {
    description = "Auto-scaling configuration optimized for AI PDF Scholar workloads"
    recommendations = [
      "Use cost-optimized nodes (spot instances) for batch processing and background tasks",
      "Use performance-optimized nodes (on-demand) for real-time API requests and RAG queries",
      "Configure pod disruption budgets to handle spot instance interruptions",
      "Use node affinity and tolerations to properly distribute workloads",
      "Monitor costs regularly and adjust instance types based on usage patterns",
      "Enable Cluster Autoscaler for automatic node provisioning and deprovisioning",
      "Consider Karpenter for advanced workload-specific node provisioning"
    ]
    cost_savings_estimate = "Up to 40% reduction in compute costs through spot instances and right-sizing"
  }
}

# Health Check Endpoints
output "health_check_endpoints" {
  description = "Health check endpoints for monitoring"
  value = {
    cluster_autoscaler_metrics = "http://cluster-autoscaler.kube-system:8085/metrics"
    aws_load_balancer_controller_metrics = "http://aws-load-balancer-controller.kube-system:8080/metrics"
    karpenter_metrics = var.enable_karpenter ? "http://karpenter.karpenter:8080/metrics" : null
  }
}

# Resource Tags
output "applied_tags" {
  description = "Tags applied to all resources for cost tracking and management"
  value = merge(var.tags, var.cost_allocation_tags, {
    "k8s.io/cluster-autoscaler/enabled" = "true"
    "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
  })
}

# Instance Type Information
output "instance_type_configuration" {
  description = "Instance type configuration for reference"
  value = {
    cost_optimized_types = aws_eks_node_group.cost_optimized.instance_types
    performance_optimized_type = var.performance_instance_type
    preferred_families = var.preferred_instance_families
    excluded_types = var.excluded_instance_types
  }
}

# Networking Configuration
output "networking_configuration" {
  description = "Networking configuration for the auto-scaled cluster"
  value = {
    vpc_id = var.vpc_id
    max_pods_per_node = var.max_pods_per_node
    pod_eni_enabled = var.enable_pod_eni
  }
}

# Security Configuration
output "security_configuration" {
  description = "Security configuration summary"
  value = {
    irsa_enabled = var.enable_irsa
    encryption_at_rest = var.enable_encryption_at_rest
    pod_security_policy = var.enable_pod_security_policy
    network_policy = var.enable_network_policy
    compliance_mode = var.compliance_mode
  }
}

# Maintenance Configuration
output "maintenance_configuration" {
  description = "Maintenance and update configuration"
  value = {
    maintenance_window = var.maintenance_window
    auto_update_enabled = var.auto_update_enabled
    backup_enabled = var.enable_backup
    backup_retention_days = var.backup_retention_days
  }
}