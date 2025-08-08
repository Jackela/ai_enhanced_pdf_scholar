# Disaster Recovery Module Variables

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ai-pdf-scholar"
}

variable "environment" {
  description = "Environment name (e.g., production, staging)"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version for EKS clusters"
  type        = string
  default     = "1.28"
}

# ============================================================================
# Region Configuration
# ============================================================================

variable "primary_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-west-2"
}

variable "secondary_region" {
  description = "Secondary AWS region for disaster recovery"
  type        = string
  default     = "us-east-1"
}

variable "tertiary_region" {
  description = "Tertiary AWS region for cold standby"
  type        = string
  default     = "eu-west-1"
}

# ============================================================================
# Secondary Region VPC Configuration
# ============================================================================

variable "secondary_availability_zones" {
  description = "Availability zones for secondary region"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "secondary_vpc_cidr" {
  description = "CIDR block for secondary region VPC"
  type        = string
  default     = "10.1.0.0/16"
}

variable "secondary_private_subnets" {
  description = "Private subnet CIDR blocks for secondary region"
  type        = list(string)
  default     = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
}

variable "secondary_public_subnets" {
  description = "Public subnet CIDR blocks for secondary region"
  type        = list(string)
  default     = ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]
}

variable "secondary_database_subnets" {
  description = "Database subnet CIDR blocks for secondary region"
  type        = list(string)
  default     = ["10.1.201.0/24", "10.1.202.0/24", "10.1.203.0/24"]
}

# ============================================================================
# Tertiary Region VPC Configuration
# ============================================================================

variable "tertiary_availability_zones" {
  description = "Availability zones for tertiary region"
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}

variable "tertiary_vpc_cidr" {
  description = "CIDR block for tertiary region VPC"
  type        = string
  default     = "10.2.0.0/16"
}

variable "tertiary_private_subnets" {
  description = "Private subnet CIDR blocks for tertiary region"
  type        = list(string)
  default     = ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24"]
}

variable "tertiary_public_subnets" {
  description = "Public subnet CIDR blocks for tertiary region"
  type        = list(string)
  default     = ["10.2.101.0/24", "10.2.102.0/24", "10.2.103.0/24"]
}

variable "tertiary_database_subnets" {
  description = "Database subnet CIDR blocks for tertiary region"
  type        = list(string)
  default     = ["10.2.201.0/24", "10.2.202.0/24", "10.2.203.0/24"]
}

# ============================================================================
# Disaster Recovery Configuration
# ============================================================================

variable "dr_max_capacity" {
  description = "Maximum capacity for DR EKS node groups"
  type        = number
  default     = 10
}

variable "dr_instance_types" {
  description = "Instance types for DR EKS nodes"
  type        = list(string)
  default     = ["t3.medium", "t3.large"]
}

variable "tertiary_max_capacity" {
  description = "Maximum capacity for tertiary EKS node groups"
  type        = number
  default     = 5
}

variable "tertiary_instance_types" {
  description = "Instance types for tertiary EKS nodes"
  type        = list(string)
  default     = ["t3.small", "t3.medium"]
}

variable "primary_db_identifier" {
  description = "Primary database identifier for creating read replica"
  type        = string
}

variable "dr_db_instance_class" {
  description = "Instance class for DR database replica"
  type        = string
  default     = "db.t3.medium"
}

variable "enable_multi_az_dr" {
  description = "Enable Multi-AZ for DR database replica"
  type        = bool
  default     = false
}

# ============================================================================
# Route 53 and DNS Configuration
# ============================================================================

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID for DNS failover"
  type        = string
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
}

variable "primary_domain" {
  description = "Primary domain for health checks"
  type        = string
}

variable "secondary_domain" {
  description = "Secondary domain for health checks"
  type        = string
}

variable "primary_ip" {
  description = "Primary IP address for DNS failover"
  type        = string
}

variable "secondary_ip" {
  description = "Secondary IP address for DNS failover"
  type        = string
}

# ============================================================================
# Notification Configuration
# ============================================================================

variable "dr_notification_email" {
  description = "Email address for disaster recovery notifications"
  type        = string
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  sensitive   = true
  default     = ""
}

# ============================================================================
# Backup Configuration
# ============================================================================

variable "backup_retention_critical" {
  description = "Retention period for critical backups in days"
  type        = number
  default     = 7
}

variable "backup_retention_high" {
  description = "Retention period for high priority backups in days"
  type        = number
  default     = 30
}

variable "backup_retention_medium" {
  description = "Retention period for medium priority backups in days"
  type        = number
  default     = 90
}

variable "backup_retention_low" {
  description = "Retention period for low priority backups in days"
  type        = number
  default     = 365
}

# ============================================================================
# Security Configuration
# ============================================================================

variable "enable_cross_region_encryption" {
  description = "Enable cross-region encryption for backups"
  type        = bool
  default     = true
}

variable "enable_backup_versioning" {
  description = "Enable versioning for backup buckets"
  type        = bool
  default     = true
}

variable "enable_mfa_delete" {
  description = "Enable MFA delete for backup buckets"
  type        = bool
  default     = true
}

# ============================================================================
# Cost Optimization
# ============================================================================

variable "enable_intelligent_tiering" {
  description = "Enable S3 Intelligent Tiering for backup buckets"
  type        = bool
  default     = true
}

variable "enable_glacier_transitions" {
  description = "Enable transitions to Glacier storage classes"
  type        = bool
  default     = true
}

variable "cold_standby_schedule" {
  description = "Schedule for cold standby resources (cron expression)"
  type        = string
  default     = "0 2 * * 0"  # Weekly on Sunday at 2 AM
}

# ============================================================================
# Monitoring Configuration
# ============================================================================

variable "health_check_failure_threshold" {
  description = "Number of consecutive health check failures before triggering failover"
  type        = number
  default     = 3
}

variable "health_check_interval" {
  description = "Health check interval in seconds"
  type        = number
  default     = 30
}

variable "cloudwatch_log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 30
}

# ============================================================================
# Compliance Configuration
# ============================================================================

variable "enable_compliance_logging" {
  description = "Enable compliance logging for DR operations"
  type        = bool
  default     = true
}

variable "enable_audit_trail" {
  description = "Enable CloudTrail for DR resource auditing"
  type        = bool
  default     = true
}

variable "enable_config_rules" {
  description = "Enable AWS Config rules for DR compliance"
  type        = bool
  default     = true
}

# ============================================================================
# Recovery Objectives
# ============================================================================

variable "rto_target_minutes" {
  description = "Recovery Time Objective target in minutes"
  type        = number
  default     = 60
}

variable "rpo_target_minutes" {
  description = "Recovery Point Objective target in minutes"
  type        = number
  default     = 15
}

variable "critical_services_rto_minutes" {
  description = "RTO for critical services in minutes"
  type        = number
  default     = 15
}

# ============================================================================
# Testing Configuration
# ============================================================================

variable "enable_automated_dr_testing" {
  description = "Enable automated disaster recovery testing"
  type        = bool
  default     = true
}

variable "dr_test_schedule" {
  description = "Schedule for automated DR testing (cron expression)"
  type        = string
  default     = "0 3 1 * *"  # Monthly on the 1st at 3 AM
}

variable "enable_test_isolation" {
  description = "Enable isolated testing environment for DR procedures"
  type        = bool
  default     = true
}

# ============================================================================
# Advanced Configuration
# ============================================================================

variable "enable_chaos_engineering" {
  description = "Enable chaos engineering for DR resilience testing"
  type        = bool
  default     = false
}

variable "enable_predictive_scaling" {
  description = "Enable predictive scaling for DR resources"
  type        = bool
  default     = false
}

variable "enable_multi_cloud_dr" {
  description = "Enable multi-cloud disaster recovery (experimental)"
  type        = bool
  default     = false
}

# ============================================================================
# Local Development Override
# ============================================================================

variable "local_development_mode" {
  description = "Enable local development mode with minimal resources"
  type        = bool
  default     = false
}