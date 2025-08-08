# Disaster Recovery Infrastructure Module
# Multi-region disaster recovery setup with automated failover

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
      configuration_aliases = [aws.primary, aws.secondary, aws.tertiary]
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"  
      version = "~> 2.0"
    }
  }
}

# Data sources for current configuration
data "aws_caller_identity" "current" {
  provider = aws.primary
}

data "aws_region" "primary" {
  provider = aws.primary
}

data "aws_region" "secondary" {
  provider = aws.secondary
}

data "aws_region" "tertiary" {
  provider = aws.tertiary
}

# Local variables
locals {
  common_tags = {
    Project              = var.project_name
    Environment         = var.environment
    ManagedBy          = "terraform"
    DisasterRecovery   = "true"
    CreatedAt          = timestamp()
  }

  backup_retention_days = {
    critical = 7
    high     = 30
    medium   = 90
    low      = 365
  }

  dr_regions = {
    primary   = data.aws_region.primary.name
    secondary = data.aws_region.secondary.name
    tertiary  = data.aws_region.tertiary.name
  }
}

# ============================================================================
# Primary Region Resources
# ============================================================================

# Enhanced S3 bucket for backups in primary region
resource "aws_s3_bucket" "primary_backup" {
  provider = aws.primary
  bucket   = "${var.project_name}-${var.environment}-backups-primary-${random_string.bucket_suffix.result}"
  
  tags = merge(local.common_tags, {
    Name   = "Primary Backup Bucket"
    Region = data.aws_region.primary.name
    Role   = "primary-backup"
  })
}

resource "aws_s3_bucket_versioning" "primary_backup" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_backup.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "primary_backup" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_backup.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "primary_backup" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_backup.id

  rule {
    id     = "backup_lifecycle"
    status = "Enabled"

    # Move to IA after 30 days
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Move to Glacier after 90 days  
    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # Move to Deep Archive after 365 days
    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    # Delete old versions after 30 days
    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    # Delete incomplete multipart uploads after 7 days
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "critical_backup_retention"
    status = "Enabled"
    
    filter {
      prefix = "critical/"
    }

    expiration {
      days = local.backup_retention_days.critical
    }
  }

  rule {
    id     = "high_backup_retention"
    status = "Enabled"
    
    filter {
      prefix = "high/"
    }

    expiration {
      days = local.backup_retention_days.high
    }
  }
}

# Cross-region replication to secondary region
resource "aws_s3_bucket_replication_configuration" "primary_to_secondary" {
  provider = aws.primary
  role     = aws_iam_role.replication.arn
  bucket   = aws_s3_bucket.primary_backup.id

  rule {
    id     = "replicate_to_secondary"
    status = "Enabled"

    destination {
      bucket = aws_s3_bucket.secondary_backup.arn
      
      # Replicate to different storage class for cost optimization
      storage_class = "STANDARD_IA"
      
      # Enable replica metadata and delete marker replication
      replica_kms_key_id = aws_kms_key.secondary.arn
      
      access_control_translation {
        owner = "Destination"
      }
    }

    # Replicate all objects
    filter {}

    # Delete marker replication
    delete_marker_replication {
      status = "Enabled"
    }
  }

  depends_on = [aws_s3_bucket_versioning.primary_backup]
}

# ============================================================================
# Secondary Region Resources (DR Primary)
# ============================================================================

# S3 bucket in secondary region for DR
resource "aws_s3_bucket" "secondary_backup" {
  provider = aws.secondary
  bucket   = "${var.project_name}-${var.environment}-backups-secondary-${random_string.bucket_suffix.result}"
  
  tags = merge(local.common_tags, {
    Name   = "Secondary Backup Bucket"
    Region = data.aws_region.secondary.name
    Role   = "secondary-backup"
  })
}

resource "aws_s3_bucket_versioning" "secondary_backup" {
  provider = aws.secondary
  bucket   = aws_s3_bucket.secondary_backup.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "secondary_backup" {
  provider = aws.secondary
  bucket   = aws_s3_bucket.secondary_backup.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.secondary.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# EKS Cluster in secondary region for DR
module "secondary_eks" {
  source = "../aws/eks"
  providers = {
    aws = aws.secondary
  }
  
  cluster_name    = "${var.project_name}-${var.environment}-dr"
  cluster_version = var.kubernetes_version
  
  vpc_id     = module.secondary_vpc.vpc_id
  subnet_ids = module.secondary_vpc.private_subnets
  
  node_groups = {
    dr_main = {
      desired_capacity = 1  # Minimal capacity for DR
      max_capacity     = var.dr_max_capacity
      min_capacity     = 1
      instance_types   = var.dr_instance_types
      
      k8s_labels = {
        Environment = var.environment
        NodeGroup   = "dr-main"
        Role        = "disaster-recovery"
      }
    }
  }
  
  tags = merge(local.common_tags, {
    Purpose = "disaster-recovery"
    Region  = data.aws_region.secondary.name
  })
}

# VPC in secondary region
module "secondary_vpc" {
  source = "../aws/vpc"
  providers = {
    aws = aws.secondary
  }
  
  environment        = var.environment
  availability_zones = var.secondary_availability_zones
  vpc_cidr          = var.secondary_vpc_cidr
  private_subnets   = var.secondary_private_subnets
  public_subnets    = var.secondary_public_subnets
  database_subnets  = var.secondary_database_subnets
  
  enable_nat_gateway = true
  enable_vpn_gateway = false
  
  tags = merge(local.common_tags, {
    Name    = "DR VPC"
    Region  = data.aws_region.secondary.name
    Purpose = "disaster-recovery"
  })
}

# RDS Read Replica in secondary region
resource "aws_db_instance" "secondary_replica" {
  provider = aws.secondary
  
  identifier = "${var.project_name}-${var.environment}-dr-replica"
  
  # Source database from primary region
  replicate_source_db = var.primary_db_identifier
  
  instance_class = var.dr_db_instance_class
  
  # Auto minor version upgrade
  auto_minor_version_upgrade = true
  
  # Backup settings (read replicas can have backups)
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  
  # Enhanced monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring_secondary.arn
  
  # Performance Insights
  performance_insights_enabled = true
  performance_insights_retention_period = 7
  
  # Security
  storage_encrypted = true
  kms_key_id       = aws_kms_key.secondary.arn
  
  # Network
  db_subnet_group_name   = module.secondary_vpc.database_subnet_group
  vpc_security_group_ids = [aws_security_group.secondary_rds.id]
  
  # Multi-AZ for DR replica (optional, for extra reliability)
  multi_az = var.enable_multi_az_dr
  
  tags = merge(local.common_tags, {
    Name    = "DR Database Replica"
    Region  = data.aws_region.secondary.name
    Purpose = "disaster-recovery"
  })
  
  lifecycle {
    ignore_changes = [
      # These will be managed by the primary database
      engine_version,
      parameter_group_name,
    ]
  }
}

# ============================================================================
# Tertiary Region Resources (DR Secondary)
# ============================================================================

# S3 bucket in tertiary region for additional DR
resource "aws_s3_bucket" "tertiary_backup" {
  provider = aws.tertiary
  bucket   = "${var.project_name}-${var.environment}-backups-tertiary-${random_string.bucket_suffix.result}"
  
  tags = merge(local.common_tags, {
    Name   = "Tertiary Backup Bucket"
    Region = data.aws_region.tertiary.name
    Role   = "tertiary-backup"
  })
}

resource "aws_s3_bucket_versioning" "tertiary_backup" {
  provider = aws.tertiary
  bucket   = aws_s3_bucket.tertiary_backup.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tertiary_backup" {
  provider = aws.tertiary
  bucket   = aws_s3_bucket.tertiary_backup.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.tertiary.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Minimal EKS cluster in tertiary region (cold standby)
module "tertiary_eks" {
  source = "../aws/eks"
  providers = {
    aws = aws.tertiary
  }
  
  cluster_name    = "${var.project_name}-${var.environment}-tertiary"
  cluster_version = var.kubernetes_version
  
  vpc_id     = module.tertiary_vpc.vpc_id
  subnet_ids = module.tertiary_vpc.private_subnets
  
  node_groups = {
    tertiary_standby = {
      desired_capacity = 0  # Cold standby
      max_capacity     = var.tertiary_max_capacity
      min_capacity     = 0
      instance_types   = var.tertiary_instance_types
      
      k8s_labels = {
        Environment = var.environment
        NodeGroup   = "tertiary-standby"
        Role        = "cold-standby"
      }
    }
  }
  
  tags = merge(local.common_tags, {
    Purpose = "cold-standby"
    Region  = data.aws_region.tertiary.name
  })
}

# Minimal VPC in tertiary region
module "tertiary_vpc" {
  source = "../aws/vpc"
  providers = {
    aws = aws.tertiary
  }
  
  environment        = var.environment
  availability_zones = var.tertiary_availability_zones
  vpc_cidr          = var.tertiary_vpc_cidr
  private_subnets   = var.tertiary_private_subnets
  public_subnets    = var.tertiary_public_subnets
  database_subnets  = var.tertiary_database_subnets
  
  enable_nat_gateway = false  # Cost optimization for standby
  enable_vpn_gateway = false
  
  tags = merge(local.common_tags, {
    Name    = "Tertiary VPC"
    Region  = data.aws_region.tertiary.name
    Purpose = "cold-standby"
  })
}

# ============================================================================
# KMS Keys for Multi-Region Encryption
# ============================================================================

# Primary KMS key
resource "aws_kms_key" "primary" {
  provider = aws.primary
  
  description             = "Primary region encryption key for ${var.project_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  tags = merge(local.common_tags, {
    Name   = "Primary Encryption Key"
    Region = data.aws_region.primary.name
  })
}

resource "aws_kms_alias" "primary" {
  provider      = aws.primary
  name          = "alias/${var.project_name}-${var.environment}-primary"
  target_key_id = aws_kms_key.primary.key_id
}

# Secondary KMS key
resource "aws_kms_key" "secondary" {
  provider = aws.secondary
  
  description             = "Secondary region encryption key for ${var.project_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  tags = merge(local.common_tags, {
    Name   = "Secondary Encryption Key"
    Region = data.aws_region.secondary.name
  })
}

resource "aws_kms_alias" "secondary" {
  provider      = aws.secondary
  name          = "alias/${var.project_name}-${var.environment}-secondary"
  target_key_id = aws_kms_key.secondary.key_id
}

# Tertiary KMS key
resource "aws_kms_key" "tertiary" {
  provider = aws.tertiary
  
  description             = "Tertiary region encryption key for ${var.project_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  tags = merge(local.common_tags, {
    Name   = "Tertiary Encryption Key"
    Region = data.aws_region.tertiary.name
  })
}

resource "aws_kms_alias" "tertiary" {
  provider      = aws.tertiary
  name          = "alias/${var.project_name}-${var.environment}-tertiary"
  target_key_id = aws_kms_key.tertiary.key_id
}

# ============================================================================
# Route 53 Health Checks and DNS Failover
# ============================================================================

# Health check for primary region
resource "aws_route53_health_check" "primary" {
  provider                            = aws.primary
  fqdn                               = var.primary_domain
  port                               = 443
  type                               = "HTTPS"
  resource_path                      = "/health"
  failure_threshold                  = 3
  request_interval                   = 30
  cloudwatch_alarm_region            = data.aws_region.primary.name
  cloudwatch_alarm_name              = aws_cloudwatch_metric_alarm.primary_health.alarm_name
  insufficient_data_health_status    = "Failure"
  
  tags = merge(local.common_tags, {
    Name   = "Primary Health Check"
    Region = data.aws_region.primary.name
  })
}

# Health check for secondary region
resource "aws_route53_health_check" "secondary" {
  provider                            = aws.secondary
  fqdn                               = var.secondary_domain
  port                               = 443
  type                               = "HTTPS"
  resource_path                      = "/health"
  failure_threshold                  = 3
  request_interval                   = 30
  cloudwatch_alarm_region            = data.aws_region.secondary.name
  cloudwatch_alarm_name              = aws_cloudwatch_metric_alarm.secondary_health.alarm_name
  insufficient_data_health_status    = "Failure"
  
  tags = merge(local.common_tags, {
    Name   = "Secondary Health Check"
    Region = data.aws_region.secondary.name
  })
}

# DNS records with failover routing
resource "aws_route53_record" "primary" {
  provider = aws.primary
  zone_id  = var.route53_zone_id
  name     = var.domain_name
  type     = "A"
  
  set_identifier = "primary"
  
  failover_routing_policy {
    type = "PRIMARY"
  }
  
  health_check_id = aws_route53_health_check.primary.id
  ttl            = 60
  records        = [var.primary_ip]
}

resource "aws_route53_record" "secondary" {
  provider = aws.primary  # Route 53 is global, managed from primary
  zone_id  = var.route53_zone_id
  name     = var.domain_name
  type     = "A"
  
  set_identifier = "secondary"
  
  failover_routing_policy {
    type = "SECONDARY"
  }
  
  health_check_id = aws_route53_health_check.secondary.id
  ttl            = 60
  records        = [var.secondary_ip]
}

# ============================================================================
# CloudWatch Alarms for Health Monitoring
# ============================================================================

# Primary region health alarm
resource "aws_cloudwatch_metric_alarm" "primary_health" {
  provider = aws.primary
  
  alarm_name          = "${var.project_name}-${var.environment}-primary-health"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = "60"
  statistic           = "Minimum"
  threshold           = "1"
  alarm_description   = "Primary region health check failure"
  alarm_actions       = [aws_sns_topic.dr_alerts_primary.arn]
  
  dimensions = {
    HealthCheckId = aws_route53_health_check.primary.id
  }
  
  tags = local.common_tags
}

# Secondary region health alarm
resource "aws_cloudwatch_metric_alarm" "secondary_health" {
  provider = aws.secondary
  
  alarm_name          = "${var.project_name}-${var.environment}-secondary-health"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = "60"
  statistic           = "Minimum"
  threshold           = "1"
  alarm_description   = "Secondary region health check failure"
  alarm_actions       = [aws_sns_topic.dr_alerts_secondary.arn]
  
  dimensions = {
    HealthCheckId = aws_route53_health_check.secondary.id
  }
  
  tags = local.common_tags
}

# ============================================================================
# SNS Topics for DR Alerts
# ============================================================================

# DR alerts topic in primary region
resource "aws_sns_topic" "dr_alerts_primary" {
  provider = aws.primary
  name     = "${var.project_name}-${var.environment}-dr-alerts-primary"
  
  tags = merge(local.common_tags, {
    Name   = "DR Alerts Primary"
    Region = data.aws_region.primary.name
  })
}

# DR alerts topic in secondary region
resource "aws_sns_topic" "dr_alerts_secondary" {
  provider = aws.secondary
  name     = "${var.project_name}-${var.environment}-dr-alerts-secondary"
  
  tags = merge(local.common_tags, {
    Name   = "DR Alerts Secondary"
    Region = data.aws_region.secondary.name
  })
}

# SNS topic subscriptions
resource "aws_sns_topic_subscription" "dr_email_primary" {
  provider = aws.primary
  topic_arn = aws_sns_topic.dr_alerts_primary.arn
  protocol  = "email"
  endpoint  = var.dr_notification_email
}

resource "aws_sns_topic_subscription" "dr_email_secondary" {
  provider = aws.secondary
  topic_arn = aws_sns_topic.dr_alerts_secondary.arn
  protocol  = "email"
  endpoint  = var.dr_notification_email
}

# ============================================================================
# Lambda Function for Automated DR Orchestration
# ============================================================================

# DR orchestration Lambda in primary region
resource "aws_lambda_function" "dr_orchestrator_primary" {
  provider = aws.primary
  
  filename         = "dr_orchestrator.zip"
  function_name    = "${var.project_name}-${var.environment}-dr-orchestrator-primary"
  role            = aws_iam_role.lambda_dr.arn
  handler         = "index.handler"
  source_code_hash = data.archive_file.dr_orchestrator.output_base64sha256
  runtime         = "python3.9"
  timeout         = 900  # 15 minutes
  
  environment {
    variables = {
      PRIMARY_REGION   = data.aws_region.primary.name
      SECONDARY_REGION = data.aws_region.secondary.name
      TERTIARY_REGION  = data.aws_region.tertiary.name
      PROJECT_NAME     = var.project_name
      ENVIRONMENT      = var.environment
    }
  }
  
  tags = merge(local.common_tags, {
    Name   = "DR Orchestrator Primary"
    Region = data.aws_region.primary.name
  })
}

# Similar DR orchestrator in secondary region
resource "aws_lambda_function" "dr_orchestrator_secondary" {
  provider = aws.secondary
  
  filename         = "dr_orchestrator.zip"
  function_name    = "${var.project_name}-${var.environment}-dr-orchestrator-secondary"
  role            = aws_iam_role.lambda_dr_secondary.arn
  handler         = "index.handler"
  source_code_hash = data.archive_file.dr_orchestrator.output_base64sha256
  runtime         = "python3.9"
  timeout         = 900
  
  environment {
    variables = {
      PRIMARY_REGION   = data.aws_region.primary.name
      SECONDARY_REGION = data.aws_region.secondary.name
      TERTIARY_REGION  = data.aws_region.tertiary.name
      PROJECT_NAME     = var.project_name
      ENVIRONMENT      = var.environment
    }
  }
  
  tags = merge(local.common_tags, {
    Name   = "DR Orchestrator Secondary"
    Region = data.aws_region.secondary.name
  })
}

# ============================================================================
# IAM Roles and Policies
# ============================================================================

# S3 replication role
resource "aws_iam_role" "replication" {
  provider = aws.primary
  name     = "${var.project_name}-${var.environment}-s3-replication"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role_policy" "replication" {
  provider = aws.primary
  name     = "${var.project_name}-${var.environment}-s3-replication-policy"
  role     = aws_iam_role.replication.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl"
        ]
        Effect = "Allow"
        Resource = [
          "${aws_s3_bucket.primary_backup.arn}/*"
        ]
      },
      {
        Action = [
          "s3:ListBucket"
        ]
        Effect = "Allow"
        Resource = [
          aws_s3_bucket.primary_backup.arn
        ]
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete"
        ]
        Effect = "Allow"
        Resource = [
          "${aws_s3_bucket.secondary_backup.arn}/*"
        ]
      }
    ]
  })
}

# RDS monitoring role for secondary region
resource "aws_iam_role" "rds_monitoring_secondary" {
  provider = aws.secondary
  name     = "${var.project_name}-${var.environment}-rds-monitoring-secondary"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring_secondary" {
  provider   = aws.secondary
  role       = aws_iam_role.rds_monitoring_secondary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Lambda DR orchestrator role
resource "aws_iam_role" "lambda_dr" {
  provider = aws.primary
  name     = "${var.project_name}-${var.environment}-lambda-dr"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role" "lambda_dr_secondary" {
  provider = aws.secondary
  name     = "${var.project_name}-${var.environment}-lambda-dr-secondary"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# Lambda DR orchestrator policy
resource "aws_iam_role_policy" "lambda_dr" {
  provider = aws.primary
  name     = "${var.project_name}-${var.environment}-lambda-dr-policy"
  role     = aws_iam_role.lambda_dr.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream", 
          "logs:PutLogEvents"
        ]
        Effect = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action = [
          "rds:DescribeDBInstances",
          "rds:PromoteReadReplica",
          "rds:CreateDBSnapshot",
          "rds:RestoreDBInstanceFromDBSnapshot"
        ]
        Effect = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "route53:GetHealthCheck",
          "route53:UpdateHealthCheck",
          "route53:ChangeResourceRecordSets"
        ]
        Effect = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "sns:Publish"
        ]
        Effect = "Allow"
        Resource = [
          aws_sns_topic.dr_alerts_primary.arn,
          aws_sns_topic.dr_alerts_secondary.arn
        ]
      }
    ]
  })
}

# Security group for secondary RDS
resource "aws_security_group" "secondary_rds" {
  provider = aws.secondary
  name     = "${var.project_name}-${var.environment}-rds-secondary"
  vpc_id   = module.secondary_vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.secondary_vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = merge(local.common_tags, {
    Name = "Secondary RDS Security Group"
  })
}

# ============================================================================
# Random Suffix for Unique S3 Bucket Names
# ============================================================================

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# ============================================================================
# Lambda Package
# ============================================================================

data "archive_file" "dr_orchestrator" {
  type        = "zip"
  output_path = "dr_orchestrator.zip"
  
  source {
    content = templatefile("${path.module}/lambda/dr_orchestrator.py.tpl", {
      project_name = var.project_name
      environment  = var.environment
    })
    filename = "index.py"
  }
}

# ============================================================================
# Auto Scaling Policies for DR
# ============================================================================

# Auto scaling target for secondary EKS node group
resource "aws_appautoscaling_target" "secondary_eks_nodes" {
  provider = aws.secondary
  
  max_capacity       = var.dr_max_capacity
  min_capacity       = 1
  resource_id        = "cluster/${module.secondary_eks.cluster_id}/nodegroup/dr_main"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "eks"
}

# Auto scaling policy for disaster recovery activation
resource "aws_appautoscaling_policy" "dr_scale_up" {
  provider = aws.secondary
  
  name               = "${var.project_name}-${var.environment}-dr-scale-up"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.secondary_eks_nodes.resource_id
  scalable_dimension = aws_appautoscaling_target.secondary_eks_nodes.scalable_dimension
  service_namespace  = aws_appautoscaling_target.secondary_eks_nodes.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 70.0

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}