terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
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
  
  backend "s3" {
    bucket         = "ai-pdf-scholar-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "ai-pdf-scholar-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "ai-pdf-scholar"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Get current AWS account and region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# VPC Module
module "vpc" {
  source = "./modules/aws/vpc"
  
  environment         = var.environment
  availability_zones  = var.availability_zones
  vpc_cidr           = var.vpc_cidr
  private_subnets    = var.private_subnets
  public_subnets     = var.public_subnets
  database_subnets   = var.database_subnets
  
  enable_nat_gateway = true
  enable_vpn_gateway = false
  enable_dns_hostnames = true
  enable_dns_support = true
  
  tags = local.common_tags
}

# EKS Module
module "eks" {
  source = "./modules/aws/eks"
  
  cluster_name    = "${var.project_name}-${var.environment}"
  cluster_version = var.kubernetes_version
  
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
  
  # Node groups
  node_groups = {
    main = {
      desired_capacity = var.eks_node_desired_capacity
      max_capacity     = var.eks_node_max_capacity
      min_capacity     = var.eks_node_min_capacity
      instance_types   = var.eks_node_instance_types
      
      k8s_labels = {
        Environment = var.environment
        NodeGroup   = "main"
      }
    }
    
    # Spot instances for cost optimization
    spot = {
      desired_capacity = var.eks_spot_node_desired_capacity
      max_capacity     = var.eks_spot_node_max_capacity
      min_capacity     = var.eks_spot_node_min_capacity
      instance_types   = var.eks_spot_node_instance_types
      capacity_type    = "SPOT"
      
      k8s_labels = {
        Environment = var.environment
        NodeGroup   = "spot"
        CapacityType = "spot"
      }
      
      taints = [{
        key    = "spot"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }
  
  tags = local.common_tags
}

# RDS Module
module "rds" {
  source = "./modules/aws/rds"
  
  identifier = "${var.project_name}-${var.environment}"
  
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.rds_instance_class
  allocated_storage = var.rds_allocated_storage
  max_allocated_storage = var.rds_max_allocated_storage
  
  db_name  = var.database_name
  username = var.database_username
  
  vpc_id = module.vpc.vpc_id
  db_subnet_group_name = module.vpc.database_subnet_group
  vpc_security_group_ids = [module.security_groups.rds_security_group_id]
  
  backup_retention_period = var.rds_backup_retention_period
  backup_window          = var.rds_backup_window
  maintenance_window     = var.rds_maintenance_window
  
  # Performance Insights
  performance_insights_enabled = true
  performance_insights_retention_period = 7
  
  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn
  
  # Read replicas for scaling
  create_read_replica = var.environment == "production" ? true : false
  read_replica_count  = var.environment == "production" ? 2 : 0
  
  tags = local.common_tags
}

# ElastiCache Redis Module
module "redis" {
  source = "./modules/aws/redis"
  
  cluster_id = "${var.project_name}-${var.environment}"
  
  engine_version       = var.redis_version
  parameter_group_name = var.redis_parameter_group_name
  node_type           = var.redis_node_type
  num_cache_nodes     = var.redis_num_cache_nodes
  
  subnet_group_name = module.vpc.elasticache_subnet_group_name
  security_group_ids = [module.security_groups.redis_security_group_id]
  
  # Backup and maintenance
  snapshot_retention_limit = var.redis_snapshot_retention_limit
  snapshot_window         = var.redis_snapshot_window
  maintenance_window      = var.redis_maintenance_window
  
  tags = local.common_tags
}

# S3 Buckets Module
module "s3" {
  source = "./modules/aws/s3"
  
  environment = var.environment
  
  # Document storage bucket
  document_bucket_name = "${var.project_name}-${var.environment}-documents"
  
  # Backup bucket
  backup_bucket_name = "${var.project_name}-${var.environment}-backups"
  
  # Logs bucket
  logs_bucket_name = "${var.project_name}-${var.environment}-logs"
  
  tags = local.common_tags
}

# Security Groups Module
module "security_groups" {
  source = "./modules/aws/security-groups"
  
  vpc_id = module.vpc.vpc_id
  environment = var.environment
  
  # CIDR blocks
  vpc_cidr_block = var.vpc_cidr
  
  tags = local.common_tags
}

# Application Load Balancer Module
module "alb" {
  source = "./modules/aws/alb"
  
  name = "${var.project_name}-${var.environment}"
  
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.public_subnets
  security_groups = [module.security_groups.alb_security_group_id]
  
  # SSL certificate
  certificate_arn = var.ssl_certificate_arn
  
  tags = local.common_tags
}

# CloudWatch Module for monitoring
module "cloudwatch" {
  source = "./modules/aws/cloudwatch"
  
  environment = var.environment
  
  # EKS cluster name for monitoring
  eks_cluster_name = module.eks.cluster_id
  
  # RDS instance identifier
  rds_instance_id = module.rds.db_instance_id
  
  # Redis cluster id
  redis_cluster_id = module.redis.cache_cluster_id
  
  tags = local.common_tags
}

# IAM roles and policies
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.project_name}-${var.environment}-rds-monitoring"

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

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Kubernetes provider configuration
data "aws_eks_cluster" "cluster" {
  name = module.eks.cluster_id
}

data "aws_eks_cluster_auth" "cluster" {
  name = module.eks.cluster_id
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.cluster.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority.0.data)
  token                  = data.aws_eks_cluster_auth.cluster.token
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.cluster.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority.0.data)
    token                  = data.aws_eks_cluster_auth.cluster.token
  }
}

# Local values
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    CreatedAt   = timestamp()
  }
}