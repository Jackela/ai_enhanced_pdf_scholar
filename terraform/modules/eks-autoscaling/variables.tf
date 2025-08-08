# ============================================================================
# EKS Auto-Scaling Module Variables
# Configuration variables for cost-optimized cluster auto-scaling
# ============================================================================

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.27"
}

variable "cluster_endpoint" {
  description = "Endpoint URL for the EKS cluster"
  type        = string
}

variable "cluster_ca_certificate" {
  description = "Base64 encoded CA certificate for the EKS cluster"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC where the cluster is deployed"
  type        = string
}

variable "node_role_arn" {
  description = "ARN of the IAM role for EKS node groups"
  type        = string
}

variable "node_security_group_ids" {
  description = "List of security group IDs for the nodes"
  type        = list(string)
}

variable "oidc_provider_arn" {
  description = "ARN of the OIDC provider for the EKS cluster"
  type        = string
}

variable "aws_region" {
  description = "AWS region where the cluster is deployed"
  type        = string
}

# Instance configuration
variable "default_instance_type" {
  description = "Default instance type for cost-optimized nodes"
  type        = string
  default     = "m5.large"
}

variable "performance_instance_type" {
  description = "Instance type for performance-optimized nodes"
  type        = string
  default     = "m5.xlarge"
}

# Cost-optimized node group configuration
variable "cost_optimized_min_size" {
  description = "Minimum number of nodes in cost-optimized node group"
  type        = number
  default     = 1
}

variable "cost_optimized_max_size" {
  description = "Maximum number of nodes in cost-optimized node group"
  type        = number
  default     = 10
}

variable "cost_optimized_desired_size" {
  description = "Desired number of nodes in cost-optimized node group"
  type        = number
  default     = 2
}

# Performance-optimized node group configuration
variable "performance_min_size" {
  description = "Minimum number of nodes in performance-optimized node group"
  type        = number
  default     = 0
}

variable "performance_max_size" {
  description = "Maximum number of nodes in performance-optimized node group"
  type        = number
  default     = 5
}

variable "performance_desired_size" {
  description = "Desired number of nodes in performance-optimized node group"
  type        = number
  default     = 1
}

# Auto-scaling configuration
variable "scale_up_cooldown" {
  description = "Cooldown period after scaling up (in seconds)"
  type        = number
  default     = 300
}

variable "scale_down_cooldown" {
  description = "Cooldown period after scaling down (in seconds)"
  type        = number
  default     = 600
}

variable "cpu_scale_up_threshold" {
  description = "CPU utilization threshold for scaling up"
  type        = number
  default     = 70
}

variable "cpu_scale_down_threshold" {
  description = "CPU utilization threshold for scaling down"
  type        = number
  default     = 30
}

variable "memory_scale_up_threshold" {
  description = "Memory utilization threshold for scaling up"
  type        = number
  default     = 75
}

variable "memory_scale_down_threshold" {
  description = "Memory utilization threshold for scaling down"
  type        = number
  default     = 35
}

# Cost optimization settings
variable "spot_instance_percentage" {
  description = "Percentage of spot instances in cost-optimized node group"
  type        = number
  default     = 80
  
  validation {
    condition     = var.spot_instance_percentage >= 0 && var.spot_instance_percentage <= 100
    error_message = "Spot instance percentage must be between 0 and 100."
  }
}

variable "spot_allocation_strategy" {
  description = "Strategy for spot instance allocation"
  type        = string
  default     = "diversified"
  
  validation {
    condition     = contains(["lowest-price", "diversified", "capacity-optimized"], var.spot_allocation_strategy)
    error_message = "Spot allocation strategy must be one of: lowest-price, diversified, capacity-optimized."
  }
}

# Advanced features
variable "enable_karpenter" {
  description = "Enable Karpenter for advanced node provisioning"
  type        = bool
  default     = false
}

variable "enable_node_termination_handler" {
  description = "Enable AWS Node Termination Handler for spot instances"
  type        = bool
  default     = true
}

variable "enable_cluster_proportional_autoscaler" {
  description = "Enable Cluster Proportional Autoscaler for core services"
  type        = bool
  default     = true
}

# Monitoring and observability
variable "enable_container_insights" {
  description = "Enable CloudWatch Container Insights for the cluster"
  type        = bool
  default     = true
}

variable "cloudwatch_log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
}

# Networking
variable "enable_pod_eni" {
  description = "Enable ENI mode for pod networking"
  type        = bool
  default     = false
}

variable "max_pods_per_node" {
  description = "Maximum number of pods per node"
  type        = number
  default     = 110
}

# Security
variable "enable_irsa" {
  description = "Enable IAM Roles for Service Accounts"
  type        = bool
  default     = true
}

variable "enable_encryption_at_rest" {
  description = "Enable encryption at rest for EBS volumes"
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "KMS key ID for EBS encryption (optional)"
  type        = string
  default     = null
}

# Node group taints and labels
variable "cost_optimized_taints" {
  description = "List of taints for cost-optimized nodes"
  type = list(object({
    key    = string
    value  = string
    effect = string
  }))
  default = [
    {
      key    = "node.kubernetes.io/lifecycle"
      value  = "spot"
      effect = "NO_SCHEDULE"
    }
  ]
}

variable "performance_taints" {
  description = "List of taints for performance-optimized nodes"
  type = list(object({
    key    = string
    value  = string
    effect = string
  }))
  default = []
}

variable "cost_optimized_labels" {
  description = "Additional labels for cost-optimized nodes"
  type        = map(string)
  default = {
    "node.kubernetes.io/lifecycle" = "spot"
    "cost-optimization"            = "enabled"
  }
}

variable "performance_labels" {
  description = "Additional labels for performance-optimized nodes"
  type        = map(string)
  default = {
    "node.kubernetes.io/lifecycle" = "on-demand"
    "performance-optimization"     = "enabled"
  }
}

# Backup and disaster recovery
variable "enable_backup" {
  description = "Enable automated backup for persistent volumes"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

# Cost tracking
variable "cost_allocation_tags" {
  description = "Additional tags for cost allocation and tracking"
  type        = map(string)
  default = {
    "CostCenter"    = "ai-pdf-scholar"
    "Environment"   = "production"
    "Application"   = "ai-enhanced-pdf-scholar"
    "CostOptimized" = "true"
  }
}

variable "budget_amount" {
  description = "Monthly budget amount for cost alerts (in USD)"
  type        = number
  default     = 500
}

variable "budget_alert_threshold" {
  description = "Budget alert threshold percentage"
  type        = number
  default     = 80
}

# Cluster autoscaler configuration
variable "cluster_autoscaler_version" {
  description = "Version of the cluster autoscaler"
  type        = string
  default     = "1.27.2"
}

variable "scale_down_delay_after_add" {
  description = "How long after scale up before scale down evaluation"
  type        = string
  default     = "10m"
}

variable "scale_down_unneeded_time" {
  description = "How long a node should be unneeded before it is eligible for scale down"
  type        = string
  default     = "10m"
}

variable "scale_down_utilization_threshold" {
  description = "Node utilization level, defined as sum of requested resources divided by capacity, below which a node can be considered for scale down"
  type        = number
  default     = 0.5
}

variable "max_node_provision_time" {
  description = "Maximum time cluster autoscaler waits for node to be provisioned"
  type        = string
  default     = "15m"
}

# Instance family preferences for cost optimization
variable "preferred_instance_families" {
  description = "Preferred instance families ordered by cost-effectiveness"
  type        = list(string)
  default     = ["m5", "m5a", "m5n", "m5ad", "m4", "t3", "t3a", "c5", "c5n", "r5", "r5a"]
}

variable "excluded_instance_types" {
  description = "Instance types to exclude from auto-scaling"
  type        = list(string)
  default     = ["t2.nano", "t2.micro", "t3.nano"]
}

# Resource limits for workload types
variable "ai_workload_resource_limits" {
  description = "Resource limits specifically for AI workloads"
  type = object({
    cpu_request    = string
    cpu_limit      = string
    memory_request = string
    memory_limit   = string
  })
  default = {
    cpu_request    = "500m"
    cpu_limit      = "2000m"
    memory_request = "1Gi"
    memory_limit   = "4Gi"
  }
}

variable "web_workload_resource_limits" {
  description = "Resource limits for web/API workloads"
  type = object({
    cpu_request    = string
    cpu_limit      = string
    memory_request = string
    memory_limit   = string
  })
  default = {
    cpu_request    = "250m"
    cpu_limit      = "1000m"
    memory_request = "512Mi"
    memory_limit   = "2Gi"
  }
}

# Common tags
variable "tags" {
  description = "A map of tags to add to all resources"
  type        = map(string)
  default = {
    Terraform   = "true"
    Environment = "production"
    Application = "ai-enhanced-pdf-scholar"
  }
}

# Maintenance and updates
variable "maintenance_window" {
  description = "Preferred maintenance window for cluster updates"
  type = object({
    day_of_week = string
    start_time  = string
    duration    = number
  })
  default = {
    day_of_week = "sunday"
    start_time  = "03:00"
    duration    = 4
  }
}

variable "auto_update_enabled" {
  description = "Enable automatic updates for the cluster"
  type        = bool
  default     = false
}

# Compliance and governance
variable "enable_pod_security_policy" {
  description = "Enable Pod Security Policy"
  type        = bool
  default     = true
}

variable "enable_network_policy" {
  description = "Enable Network Policy enforcement"
  type        = bool
  default     = true
}

variable "compliance_mode" {
  description = "Compliance mode for the cluster (none, hipaa, pci, sox)"
  type        = string
  default     = "none"
  
  validation {
    condition     = contains(["none", "hipaa", "pci", "sox"], var.compliance_mode)
    error_message = "Compliance mode must be one of: none, hipaa, pci, sox."
  }
}