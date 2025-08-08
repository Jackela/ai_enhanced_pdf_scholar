# Disaster Recovery Module Outputs

# ============================================================================
# S3 Backup Buckets
# ============================================================================

output "primary_backup_bucket_id" {
  description = "Primary backup bucket ID"
  value       = aws_s3_bucket.primary_backup.id
}

output "primary_backup_bucket_arn" {
  description = "Primary backup bucket ARN"
  value       = aws_s3_bucket.primary_backup.arn
}

output "secondary_backup_bucket_id" {
  description = "Secondary backup bucket ID"
  value       = aws_s3_bucket.secondary_backup.id
}

output "secondary_backup_bucket_arn" {
  description = "Secondary backup bucket ARN"
  value       = aws_s3_bucket.secondary_backup.arn
}

output "tertiary_backup_bucket_id" {
  description = "Tertiary backup bucket ID"
  value       = aws_s3_bucket.tertiary_backup.id
}

output "tertiary_backup_bucket_arn" {
  description = "Tertiary backup bucket ARN"
  value       = aws_s3_bucket.tertiary_backup.arn
}

# ============================================================================
# EKS Clusters
# ============================================================================

output "secondary_eks_cluster_id" {
  description = "Secondary region EKS cluster ID"
  value       = module.secondary_eks.cluster_id
}

output "secondary_eks_cluster_arn" {
  description = "Secondary region EKS cluster ARN"
  value       = module.secondary_eks.cluster_arn
}

output "secondary_eks_cluster_endpoint" {
  description = "Secondary region EKS cluster endpoint"
  value       = module.secondary_eks.cluster_endpoint
}

output "secondary_eks_cluster_security_group_id" {
  description = "Secondary region EKS cluster security group ID"
  value       = module.secondary_eks.cluster_security_group_id
}

output "tertiary_eks_cluster_id" {
  description = "Tertiary region EKS cluster ID"
  value       = module.tertiary_eks.cluster_id
}

output "tertiary_eks_cluster_arn" {
  description = "Tertiary region EKS cluster ARN"
  value       = module.tertiary_eks.cluster_arn
}

output "tertiary_eks_cluster_endpoint" {
  description = "Tertiary region EKS cluster endpoint"
  value       = module.tertiary_eks.cluster_endpoint
}

# ============================================================================
# Database Replicas
# ============================================================================

output "secondary_db_replica_id" {
  description = "Secondary region database replica ID"
  value       = aws_db_instance.secondary_replica.id
}

output "secondary_db_replica_arn" {
  description = "Secondary region database replica ARN"
  value       = aws_db_instance.secondary_replica.arn
}

output "secondary_db_replica_endpoint" {
  description = "Secondary region database replica endpoint"
  value       = aws_db_instance.secondary_replica.endpoint
  sensitive   = true
}

output "secondary_db_replica_address" {
  description = "Secondary region database replica address"
  value       = aws_db_instance.secondary_replica.address
  sensitive   = true
}

# ============================================================================
# VPCs
# ============================================================================

output "secondary_vpc_id" {
  description = "Secondary region VPC ID"
  value       = module.secondary_vpc.vpc_id
}

output "secondary_vpc_cidr_block" {
  description = "Secondary region VPC CIDR block"
  value       = module.secondary_vpc.vpc_cidr_block
}

output "secondary_private_subnets" {
  description = "Secondary region private subnet IDs"
  value       = module.secondary_vpc.private_subnets
}

output "secondary_public_subnets" {
  description = "Secondary region public subnet IDs"
  value       = module.secondary_vpc.public_subnets
}

output "tertiary_vpc_id" {
  description = "Tertiary region VPC ID"
  value       = module.tertiary_vpc.vpc_id
}

output "tertiary_vpc_cidr_block" {
  description = "Tertiary region VPC CIDR block"
  value       = module.tertiary_vpc.vpc_cidr_block
}

# ============================================================================
# KMS Keys
# ============================================================================

output "primary_kms_key_id" {
  description = "Primary region KMS key ID"
  value       = aws_kms_key.primary.key_id
}

output "primary_kms_key_arn" {
  description = "Primary region KMS key ARN"
  value       = aws_kms_key.primary.arn
}

output "secondary_kms_key_id" {
  description = "Secondary region KMS key ID"
  value       = aws_kms_key.secondary.key_id
}

output "secondary_kms_key_arn" {
  description = "Secondary region KMS key ARN"
  value       = aws_kms_key.secondary.arn
}

output "tertiary_kms_key_id" {
  description = "Tertiary region KMS key ID"
  value       = aws_kms_key.tertiary.key_id
}

output "tertiary_kms_key_arn" {
  description = "Tertiary region KMS key ARN"
  value       = aws_kms_key.tertiary.arn
}

# ============================================================================
# Route 53 Health Checks
# ============================================================================

output "primary_health_check_id" {
  description = "Primary region Route 53 health check ID"
  value       = aws_route53_health_check.primary.id
}

output "secondary_health_check_id" {
  description = "Secondary region Route 53 health check ID"
  value       = aws_route53_health_check.secondary.id
}

# ============================================================================
# CloudWatch Alarms
# ============================================================================

output "primary_health_alarm_arn" {
  description = "Primary region health alarm ARN"
  value       = aws_cloudwatch_metric_alarm.primary_health.arn
}

output "secondary_health_alarm_arn" {
  description = "Secondary region health alarm ARN"
  value       = aws_cloudwatch_metric_alarm.secondary_health.arn
}

# ============================================================================
# SNS Topics
# ============================================================================

output "primary_dr_alerts_topic_arn" {
  description = "Primary region DR alerts SNS topic ARN"
  value       = aws_sns_topic.dr_alerts_primary.arn
}

output "secondary_dr_alerts_topic_arn" {
  description = "Secondary region DR alerts SNS topic ARN"
  value       = aws_sns_topic.dr_alerts_secondary.arn
}

# ============================================================================
# Lambda Functions
# ============================================================================

output "primary_dr_orchestrator_function_name" {
  description = "Primary region DR orchestrator Lambda function name"
  value       = aws_lambda_function.dr_orchestrator_primary.function_name
}

output "primary_dr_orchestrator_function_arn" {
  description = "Primary region DR orchestrator Lambda function ARN"
  value       = aws_lambda_function.dr_orchestrator_primary.arn
}

output "secondary_dr_orchestrator_function_name" {
  description = "Secondary region DR orchestrator Lambda function name"
  value       = aws_lambda_function.dr_orchestrator_secondary.function_name
}

output "secondary_dr_orchestrator_function_arn" {
  description = "Secondary region DR orchestrator Lambda function ARN"
  value       = aws_lambda_function.dr_orchestrator_secondary.arn
}

# ============================================================================
# Security Groups
# ============================================================================

output "secondary_rds_security_group_id" {
  description = "Secondary region RDS security group ID"
  value       = aws_security_group.secondary_rds.id
}

# ============================================================================
# IAM Roles
# ============================================================================

output "s3_replication_role_arn" {
  description = "S3 replication IAM role ARN"
  value       = aws_iam_role.replication.arn
}

output "lambda_dr_role_arn" {
  description = "Lambda DR orchestrator IAM role ARN"
  value       = aws_iam_role.lambda_dr.arn
}

output "secondary_rds_monitoring_role_arn" {
  description = "Secondary region RDS monitoring IAM role ARN"
  value       = aws_iam_role.rds_monitoring_secondary.arn
}

# ============================================================================
# Region Information
# ============================================================================

output "regions_configured" {
  description = "List of configured AWS regions"
  value = {
    primary   = data.aws_region.primary.name
    secondary = data.aws_region.secondary.name
    tertiary  = data.aws_region.tertiary.name
  }
}

# ============================================================================
# Disaster Recovery Configuration Summary
# ============================================================================

output "dr_configuration_summary" {
  description = "Summary of disaster recovery configuration"
  value = {
    rto_target_minutes                = var.rto_target_minutes
    rpo_target_minutes               = var.rpo_target_minutes
    critical_services_rto_minutes    = var.critical_services_rto_minutes
    health_check_failure_threshold   = var.health_check_failure_threshold
    health_check_interval_seconds    = var.health_check_interval
    backup_retention_critical_days   = var.backup_retention_critical
    backup_retention_high_days       = var.backup_retention_high
    backup_retention_medium_days     = var.backup_retention_medium
    backup_retention_low_days        = var.backup_retention_low
    cross_region_encryption_enabled  = var.enable_cross_region_encryption
    automated_dr_testing_enabled     = var.enable_automated_dr_testing
    multi_az_dr_enabled             = var.enable_multi_az_dr
  }
}

# ============================================================================
# Connection Information
# ============================================================================

output "kubeconfig_secondary" {
  description = "kubectl configuration command for secondary EKS cluster"
  value       = "aws eks --region ${data.aws_region.secondary.name} update-kubeconfig --name ${module.secondary_eks.cluster_id}"
}

output "kubeconfig_tertiary" {
  description = "kubectl configuration command for tertiary EKS cluster"
  value       = "aws eks --region ${data.aws_region.tertiary.name} update-kubeconfig --name ${module.tertiary_eks.cluster_id}"
}

# ============================================================================
# Monitoring and Alerting Endpoints
# ============================================================================

output "monitoring_endpoints" {
  description = "Monitoring and alerting endpoints"
  value = {
    primary_health_check_url   = "https://${var.primary_domain}/health"
    secondary_health_check_url = "https://${var.secondary_domain}/health"
    primary_cloudwatch_dashboard = "https://${data.aws_region.primary.name}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.primary.name}#dashboards:name=${var.project_name}-${var.environment}-dr-primary"
    secondary_cloudwatch_dashboard = "https://${data.aws_region.secondary.name}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.secondary.name}#dashboards:name=${var.project_name}-${var.environment}-dr-secondary"
  }
}

# ============================================================================
# Cost Estimation
# ============================================================================

output "estimated_monthly_cost_usd" {
  description = "Estimated monthly cost for DR infrastructure (USD)"
  value = {
    secondary_eks_cluster_minimum = 73    # Control plane cost
    secondary_rds_replica        = 50     # t3.medium estimate
    s3_storage_replication       = 25     # 1TB estimate
    route53_health_checks        = 1      # 2 health checks
    lambda_orchestrator          = 2      # Minimal usage
    cloudwatch_alarms           = 1       # 4 alarms
    data_transfer               = 20      # Cross-region transfer estimate
    total_minimum_monthly       = 172     # Sum of above
    note = "Costs will vary based on actual usage, data volume, and compute requirements"
  }
}

# ============================================================================
# Disaster Recovery Runbook
# ============================================================================

output "dr_runbook" {
  description = "Disaster recovery operational runbook"
  value = {
    manual_failover_steps = [
      "1. Assess primary region status using health checks",
      "2. Verify secondary region readiness: aws eks --region ${data.aws_region.secondary.name} describe-cluster --name ${module.secondary_eks.cluster_id}",
      "3. Promote RDS read replica: aws rds --region ${data.aws_region.secondary.name} promote-read-replica --db-instance-identifier ${aws_db_instance.secondary_replica.id}",
      "4. Update DNS records to point to secondary region",
      "5. Scale up secondary EKS cluster node groups",
      "6. Deploy application to secondary cluster",
      "7. Validate services and run health checks",
      "8. Communicate status to stakeholders"
    ]
    
    automated_failover_trigger = "Lambda function: ${aws_lambda_function.dr_orchestrator_primary.function_name}"
    
    rollback_steps = [
      "1. Ensure primary region is fully operational",
      "2. Sync data from secondary back to primary (if needed)",
      "3. Update DNS records to point back to primary",
      "4. Scale down secondary region resources",
      "5. Re-establish RDS read replica from primary to secondary"
    ]
    
    testing_schedule = var.dr_test_schedule
    
    emergency_contacts = {
      email = var.dr_notification_email
      slack = var.slack_webhook_url != "" ? "Configured" : "Not configured"
    }
  }
}