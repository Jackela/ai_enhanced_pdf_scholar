# AI Enhanced PDF Scholar - Terraform Outputs

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnets
}

output "database_subnets" {
  description = "List of IDs of database subnets"
  value       = module.vpc.database_subnets
}

# EKS Outputs
output "cluster_id" {
  description = "EKS cluster ID"
  value       = module.eks.cluster_id
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks.cluster_arn
}

output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "cluster_iam_role_name" {
  description = "IAM role name associated with EKS cluster"
  value       = module.eks.cluster_iam_role_name
}

output "cluster_iam_role_arn" {
  description = "IAM role ARN associated with EKS cluster"
  value       = module.eks.cluster_iam_role_arn
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = module.eks.cluster_certificate_authority_data
}

output "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster OIDC Issuer"
  value       = module.eks.cluster_oidc_issuer_url
}

output "node_groups" {
  description = "EKS node groups"
  value       = module.eks.node_groups
}

# RDS Outputs
output "rds_cluster_endpoint" {
  description = "RDS cluster endpoint"
  value       = module.rds.cluster_endpoint
  sensitive   = true
}

output "rds_cluster_reader_endpoint" {
  description = "RDS cluster reader endpoint"
  value       = module.rds.cluster_reader_endpoint
  sensitive   = true
}

output "rds_cluster_engine_version" {
  description = "The engine version of the RDS cluster"
  value       = module.rds.cluster_engine_version
}

output "rds_cluster_database_name" {
  description = "The database name"
  value       = module.rds.cluster_database_name
}

output "rds_cluster_port" {
  description = "The database port"
  value       = module.rds.cluster_port
}

output "rds_cluster_master_username" {
  description = "The database master username"
  value       = module.rds.cluster_master_username
  sensitive   = true
}

output "rds_security_group_id" {
  description = "The security group ID of the cluster"
  value       = module.security_groups.rds_security_group_id
}

# ElastiCache Outputs
output "elasticache_cluster_address" {
  description = "Redis primary endpoint"
  value       = module.elasticache.cluster_address
  sensitive   = true
}

output "elasticache_cluster_port" {
  description = "Redis port"
  value       = module.elasticache.port
}

output "elasticache_security_group_id" {
  description = "ElastiCache security group ID"
  value       = module.security_groups.elasticache_security_group_id
}

# S3 Outputs
output "s3_uploads_bucket_id" {
  description = "The name of the uploads bucket"
  value       = module.s3.uploads_bucket_id
}

output "s3_uploads_bucket_arn" {
  description = "The ARN of the uploads bucket"
  value       = module.s3.uploads_bucket_arn
}

output "s3_backup_bucket_id" {
  description = "The name of the backup bucket"
  value       = module.s3.backup_bucket_id
}

output "s3_backup_bucket_arn" {
  description = "The ARN of the backup bucket"
  value       = module.s3.backup_bucket_arn
}

# Secrets Manager Outputs
output "secrets_manager_arn" {
  description = "The ARN of the secrets in Secrets Manager"
  value       = module.secrets.secrets_arn
  sensitive   = true
}

output "database_credentials_secret_arn" {
  description = "ARN of the database credentials secret"
  value       = module.secrets.database_credentials_secret_arn
  sensitive   = true
}

output "application_secrets_arn" {
  description = "ARN of the application secrets"
  value       = module.secrets.application_secrets_arn
  sensitive   = true
}

# IAM Outputs
output "iam_role_application_arn" {
  description = "ARN of the IAM role for the application"
  value       = module.iam_roles.application_role_arn
}

output "iam_role_application_name" {
  description = "Name of the IAM role for the application"
  value       = module.iam_roles.application_role_name
}

output "iam_role_monitoring_arn" {
  description = "ARN of the IAM role for monitoring services"
  value       = module.iam_roles.monitoring_role_arn
}

# Load Balancer Outputs
output "alb_arn" {
  description = "The ARN of the load balancer"
  value       = module.alb.arn
}

output "alb_dns_name" {
  description = "The DNS name of the load balancer"
  value       = module.alb.dns_name
}

output "alb_zone_id" {
  description = "The zone ID of the load balancer"
  value       = module.alb.zone_id
}

output "alb_security_group_id" {
  description = "Security group ID attached to the ALB"
  value       = module.security_groups.alb_security_group_id
}

# Route 53 Outputs (if domain is configured)
output "route53_zone_id" {
  description = "Zone ID of Route 53 hosted zone"
  value       = var.domain_name != "" ? module.route53[0].zone_id : null
}

output "route53_name_servers" {
  description = "Name servers for the Route 53 hosted zone"
  value       = var.domain_name != "" ? module.route53[0].name_servers : null
}

# CloudWatch Outputs
output "cloudwatch_log_group_application_name" {
  description = "Name of the application CloudWatch log group"
  value       = aws_cloudwatch_log_group.application.name
}

output "cloudwatch_log_group_audit_name" {
  description = "Name of the audit CloudWatch log group"
  value       = aws_cloudwatch_log_group.audit.name
}

# Application URLs
output "application_url" {
  description = "URL to access the application"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "https://${module.alb.dns_name}"
}

# Kubernetes Configuration
output "kubectl_config" {
  description = "kubectl config as generated by the module"
  value = {
    cluster_name                         = module.eks.cluster_id
    cluster_endpoint                     = module.eks.cluster_endpoint
    cluster_certificate_authority_data  = module.eks.cluster_certificate_authority_data
  }
  sensitive = true
}

# Monitoring Endpoints
output "monitoring_endpoints" {
  description = "Monitoring service endpoints"
  value = {
    prometheus = var.enable_prometheus ? "http://prometheus.${local.cluster_name}.local:9090" : null
    grafana    = var.enable_grafana ? "http://grafana.${local.cluster_name}.local:3000" : null
    jaeger     = var.enable_jaeger ? "http://jaeger.${local.cluster_name}.local:16686" : null
    kibana     = var.enable_elasticsearch ? "http://kibana.${local.cluster_name}.local:5601" : null
  }
}

# Security Information
output "security_configuration" {
  description = "Security configuration summary"
  value = {
    waf_enabled       = var.enable_waf
    shield_enabled    = var.enable_shield
    guardduty_enabled = var.enable_guardduty
    ssl_enabled       = var.ssl_certificate_arn != ""
    encryption_at_rest = {
      rds           = true
      elasticache   = true
      s3            = true
      ebs           = true
    }
    encryption_in_transit = {
      alb_to_pods   = var.ssl_certificate_arn != ""
      rds           = true
      elasticache   = true
      s3            = true
    }
  }
}

# Cost Information
output "cost_optimization" {
  description = "Cost optimization features enabled"
  value = {
    spot_instances_enabled      = var.enable_spot_instances
    scheduled_scaling_enabled   = var.enable_scheduled_scaling
    multi_az_deployment        = var.multi_az_deployment
    automated_backups_enabled  = var.enable_automated_backups
    backup_retention_days      = var.backup_retention_days
  }
}

# Environment Information
output "environment_info" {
  description = "Environment information"
  value = {
    environment          = var.environment
    region              = local.region
    account_id          = local.account_id
    cluster_name        = local.cluster_name
    vpc_cidr            = local.vpc_cidr
    availability_zones  = slice(data.aws_availability_zones.available.names, 0, 3)
  }
}