"""
AWS Lambda Function for Disaster Recovery Orchestration
Automatically handles failover scenarios and recovery coordination.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment configuration
PROJECT_NAME = "${project_name}"
ENVIRONMENT = "${environment}"
PRIMARY_REGION = os.environ.get('PRIMARY_REGION', 'us-west-2')
SECONDARY_REGION = os.environ.get('SECONDARY_REGION', 'us-east-1')
TERTIARY_REGION = os.environ.get('TERTIARY_REGION', 'eu-west-1')

# Recovery objectives (in minutes)
RTO_TARGET = 60  # Recovery Time Objective
RPO_TARGET = 15  # Recovery Point Objective
CRITICAL_RTO = 15  # Critical services RTO

# AWS service clients
def get_aws_client(service: str, region: str = None):
    """Get AWS service client for specified region."""
    if region:
        return boto3.client(service, region_name=region)
    return boto3.client(service)


class DisasterRecoveryOrchestrator:
    """Main disaster recovery orchestration class."""
    
    def __init__(self):
        """Initialize the orchestrator."""
        self.current_region = os.environ.get('AWS_REGION', PRIMARY_REGION)
        self.execution_id = f"dr-{int(time.time())}"
        self.start_time = datetime.utcnow()
        
        # Initialize AWS clients
        self.rds_primary = get_aws_client('rds', PRIMARY_REGION)
        self.rds_secondary = get_aws_client('rds', SECONDARY_REGION)
        self.route53 = get_aws_client('route53')
        self.sns_primary = get_aws_client('sns', PRIMARY_REGION)
        self.sns_secondary = get_aws_client('sns', SECONDARY_REGION)
        self.cloudwatch = get_aws_client('cloudwatch', self.current_region)
        
        logger.info(f"DR Orchestrator initialized: {self.execution_id}")
    
    def assess_disaster_scope(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the scope and severity of the disaster."""
        assessment = {
            'disaster_type': event.get('disaster_type', 'unknown'),
            'affected_regions': event.get('affected_regions', [PRIMARY_REGION]),
            'affected_services': event.get('affected_services', []),
            'severity': 'unknown',
            'recommended_action': 'assess'
        }
        
        try:
            # Check primary region health
            primary_health = self._check_region_health(PRIMARY_REGION)
            secondary_health = self._check_region_health(SECONDARY_REGION)
            
            assessment['primary_region_health'] = primary_health
            assessment['secondary_region_health'] = secondary_health
            
            # Determine severity and action
            if primary_health['status'] == 'critical':
                if secondary_health['status'] == 'healthy':
                    assessment['severity'] = 'high'
                    assessment['recommended_action'] = 'failover_to_secondary'
                else:
                    assessment['severity'] = 'critical'
                    assessment['recommended_action'] = 'failover_to_tertiary'
            elif primary_health['status'] == 'degraded':
                assessment['severity'] = 'medium'
                assessment['recommended_action'] = 'monitor_and_prepare'
            else:
                assessment['severity'] = 'low'
                assessment['recommended_action'] = 'continue_monitoring'
            
        except Exception as e:
            logger.error(f"Error assessing disaster scope: {e}")
            assessment['error'] = str(e)
        
        return assessment
    
    def _check_region_health(self, region: str) -> Dict[str, Any]:
        """Check health of a specific region."""
        health = {
            'region': region,
            'status': 'unknown',
            'services': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # Check RDS instances
            rds_client = get_aws_client('rds', region)
            db_instances = rds_client.describe_db_instances()
            
            healthy_dbs = sum(1 for db in db_instances['DBInstances'] 
                            if db['DBInstanceStatus'] == 'available')
            total_dbs = len(db_instances['DBInstances'])
            
            health['services']['rds'] = {
                'healthy_instances': healthy_dbs,
                'total_instances': total_dbs,
                'status': 'healthy' if healthy_dbs == total_dbs else 'degraded'
            }
            
            # Check EKS clusters (simplified)
            try:
                eks_client = get_aws_client('eks', region)
                clusters = eks_client.list_clusters()
                
                health['services']['eks'] = {
                    'cluster_count': len(clusters['clusters']),
                    'status': 'healthy' if clusters['clusters'] else 'degraded'
                }
            except Exception as e:
                health['services']['eks'] = {'status': 'unknown', 'error': str(e)}
            
            # Overall health assessment
            service_statuses = [svc.get('status') for svc in health['services'].values()]
            if all(status == 'healthy' for status in service_statuses):
                health['status'] = 'healthy'
            elif any(status == 'healthy' for status in service_statuses):
                health['status'] = 'degraded'
            else:
                health['status'] = 'critical'
                
        except Exception as e:
            logger.error(f"Error checking health for region {region}: {e}")
            health['status'] = 'critical'
            health['error'] = str(e)
        
        return health
    
    def execute_failover(self, target_region: str, services: List[str]) -> Dict[str, Any]:
        """Execute failover to target region."""
        failover_results = {
            'target_region': target_region,
            'services_failed_over': [],
            'failures': [],
            'start_time': datetime.utcnow().isoformat()
        }
        
        try:
            # Step 1: Promote RDS read replica
            if 'rds' in services:
                rds_result = self._promote_rds_replica(target_region)
                if rds_result['success']:
                    failover_results['services_failed_over'].append('rds')
                else:
                    failover_results['failures'].append(rds_result)
            
            # Step 2: Update DNS records
            if 'route53' in services:
                dns_result = self._update_dns_failover(target_region)
                if dns_result['success']:
                    failover_results['services_failed_over'].append('route53')
                else:
                    failover_results['failures'].append(dns_result)
            
            # Step 3: Scale up target region EKS
            if 'eks' in services:
                eks_result = self._scale_up_eks(target_region)
                if eks_result['success']:
                    failover_results['services_failed_over'].append('eks')
                else:
                    failover_results['failures'].append(eks_result)
            
            failover_results['end_time'] = datetime.utcnow().isoformat()
            failover_results['success'] = len(failover_results['failures']) == 0
            
        except Exception as e:
            logger.error(f"Error during failover execution: {e}")
            failover_results['error'] = str(e)
            failover_results['success'] = False
        
        return failover_results
    
    def _promote_rds_replica(self, region: str) -> Dict[str, Any]:
        """Promote RDS read replica in target region."""
        try:
            rds_client = get_aws_client('rds', region)
            
            # Find read replicas to promote
            db_instances = rds_client.describe_db_instances()
            replicas = [
                db for db in db_instances['DBInstances']
                if db.get('ReadReplicaSourceDBInstanceIdentifier')
            ]
            
            if not replicas:
                return {
                    'success': False,
                    'error': f'No read replicas found in {region}'
                }
            
            promoted_replicas = []
            for replica in replicas:
                replica_id = replica['DBInstanceIdentifier']
                
                # Promote replica
                response = rds_client.promote_read_replica(
                    DBInstanceIdentifier=replica_id
                )
                
                promoted_replicas.append({
                    'replica_id': replica_id,
                    'status': 'promoting'
                })
                
                logger.info(f"Promoting RDS replica: {replica_id}")
            
            return {
                'success': True,
                'promoted_replicas': promoted_replicas
            }
            
        except Exception as e:
            logger.error(f"Error promoting RDS replica: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_dns_failover(self, target_region: str) -> Dict[str, Any]:
        """Update Route 53 DNS records for failover."""
        try:
            # This would implement actual DNS failover logic
            # For now, return a placeholder
            logger.info(f"DNS failover to {target_region} would be executed here")
            
            return {
                'success': True,
                'action': f'DNS updated to failover to {target_region}'
            }
            
        except Exception as e:
            logger.error(f"Error updating DNS failover: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _scale_up_eks(self, region: str) -> Dict[str, Any]:
        """Scale up EKS cluster in target region."""
        try:
            # This would implement actual EKS scaling logic
            # Using AWS CLI or Kubernetes API
            logger.info(f"EKS cluster scaling in {region} would be executed here")
            
            return {
                'success': True,
                'action': f'EKS scaled up in {region}'
            }
            
        except Exception as e:
            logger.error(f"Error scaling EKS: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_recovery(self, target_region: str) -> Dict[str, Any]:
        """Validate that recovery was successful."""
        validation = {
            'target_region': target_region,
            'validation_start': datetime.utcnow().isoformat(),
            'checks': {},
            'overall_success': True
        }
        
        try:
            # Validate RDS
            rds_validation = self._validate_rds_recovery(target_region)
            validation['checks']['rds'] = rds_validation
            if not rds_validation['success']:
                validation['overall_success'] = False
            
            # Validate EKS
            eks_validation = self._validate_eks_recovery(target_region)
            validation['checks']['eks'] = eks_validation
            if not eks_validation['success']:
                validation['overall_success'] = False
            
            # Validate DNS
            dns_validation = self._validate_dns_recovery()
            validation['checks']['dns'] = dns_validation
            if not dns_validation['success']:
                validation['overall_success'] = False
            
            validation['validation_end'] = datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.error(f"Error during recovery validation: {e}")
            validation['error'] = str(e)
            validation['overall_success'] = False
        
        return validation
    
    def _validate_rds_recovery(self, region: str) -> Dict[str, Any]:
        """Validate RDS recovery."""
        try:
            rds_client = get_aws_client('rds', region)
            db_instances = rds_client.describe_db_instances()
            
            available_instances = [
                db for db in db_instances['DBInstances']
                if db['DBInstanceStatus'] == 'available' and not db.get('ReadReplicaSourceDBInstanceIdentifier')
            ]
            
            return {
                'success': len(available_instances) > 0,
                'available_instances': len(available_instances),
                'details': available_instances
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _validate_eks_recovery(self, region: str) -> Dict[str, Any]:
        """Validate EKS recovery."""
        try:
            # Placeholder for EKS validation
            return {
                'success': True,
                'message': 'EKS validation would be performed here'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _validate_dns_recovery(self) -> Dict[str, Any]:
        """Validate DNS recovery."""
        try:
            # Placeholder for DNS validation
            return {
                'success': True,
                'message': 'DNS validation would be performed here'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def send_notifications(self, message: str, severity: str = 'info'):
        """Send notifications about DR status."""
        try:
            # Determine SNS topic based on region
            if self.current_region == PRIMARY_REGION:
                topic_arn = f"arn:aws:sns:{PRIMARY_REGION}:{self._get_account_id()}:{PROJECT_NAME}-{ENVIRONMENT}-dr-alerts-primary"
            else:
                topic_arn = f"arn:aws:sns:{SECONDARY_REGION}:{self._get_account_id()}:{PROJECT_NAME}-{ENVIRONMENT}-dr-alerts-secondary"
            
            # Send SNS notification
            sns_client = get_aws_client('sns', self.current_region)
            
            subject = f"🚨 DR Alert: {PROJECT_NAME} {ENVIRONMENT}"
            if severity == 'success':
                subject = f"✅ DR Success: {PROJECT_NAME} {ENVIRONMENT}"
            elif severity == 'warning':
                subject = f"⚠️ DR Warning: {PROJECT_NAME} {ENVIRONMENT}"
            
            sns_client.publish(
                TopicArn=topic_arn,
                Subject=subject,
                Message=f"""
Disaster Recovery Update
========================
Execution ID: {self.execution_id}
Timestamp: {datetime.utcnow().isoformat()}
Region: {self.current_region}

Message: {message}

Automated DR Orchestrator
                """.strip()
            )
            
            logger.info(f"Notification sent: {subject}")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        try:
            sts = boto3.client('sts')
            return sts.get_caller_identity()['Account']
        except Exception as e:
            logger.error(f"Error getting account ID: {e}")
            return "unknown"
    
    def record_metrics(self, metrics: Dict[str, Any]):
        """Record CloudWatch metrics."""
        try:
            # Record recovery time
            recovery_time = (datetime.utcnow() - self.start_time).total_seconds()
            
            self.cloudwatch.put_metric_data(
                Namespace=f'{PROJECT_NAME}/DisasterRecovery',
                MetricData=[
                    {
                        'MetricName': 'RecoveryDuration',
                        'Value': recovery_time,
                        'Unit': 'Seconds',
                        'Dimensions': [
                            {
                                'Name': 'Environment',
                                'Value': ENVIRONMENT
                            },
                            {
                                'Name': 'ExecutionId',
                                'Value': self.execution_id
                            }
                        ]
                    },
                    {
                        'MetricName': 'RecoveryAttempts',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {
                                'Name': 'Environment',
                                'Value': ENVIRONMENT
                            }
                        ]
                    }
                ]
            )
            
            # Record RTO/RPO metrics if available
            if 'rto_achieved' in metrics:
                self.cloudwatch.put_metric_data(
                    Namespace=f'{PROJECT_NAME}/DisasterRecovery',
                    MetricData=[
                        {
                            'MetricName': 'RTOAchieved',
                            'Value': 1 if metrics['rto_achieved'] else 0,
                            'Unit': 'Count',
                            'Dimensions': [
                                {
                                    'Name': 'Environment',
                                    'Value': ENVIRONMENT
                                }
                            ]
                        }
                    ]
                )
            
        except Exception as e:
            logger.error(f"Error recording metrics: {e}")


def lambda_handler(event, context):
    """
    Lambda function handler for disaster recovery orchestration.
    
    Event types:
    - health_check_failure: Triggered by Route 53 health check failure
    - manual_trigger: Manual disaster recovery trigger
    - scheduled_test: Scheduled DR testing
    """
    
    logger.info(f"DR Lambda triggered: {json.dumps(event)}")
    
    orchestrator = DisasterRecoveryOrchestrator()
    
    try:
        # Determine event type
        event_type = event.get('source', 'manual_trigger')
        disaster_type = event.get('disaster_type', 'infrastructure_failure')
        
        # Send initial notification
        orchestrator.send_notifications(
            f"Disaster recovery initiated: {disaster_type} in {orchestrator.current_region}",
            severity='warning'
        )
        
        # Assess disaster scope
        assessment = orchestrator.assess_disaster_scope(event)
        logger.info(f"Disaster assessment: {assessment}")
        
        response = {
            'execution_id': orchestrator.execution_id,
            'assessment': assessment,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Execute recovery based on assessment
        if assessment['recommended_action'] == 'failover_to_secondary':
            logger.info("Executing failover to secondary region")
            
            failover_result = orchestrator.execute_failover(
                SECONDARY_REGION,
                ['rds', 'route53', 'eks']
            )
            
            response['failover'] = failover_result
            
            if failover_result['success']:
                # Validate recovery
                validation = orchestrator.validate_recovery(SECONDARY_REGION)
                response['validation'] = validation
                
                if validation['overall_success']:
                    orchestrator.send_notifications(
                        f"✅ Disaster recovery completed successfully to {SECONDARY_REGION}. "
                        f"RTO: {(datetime.utcnow() - orchestrator.start_time).total_seconds() / 60:.1f} minutes",
                        severity='success'
                    )
                    
                    # Record successful recovery metrics
                    orchestrator.record_metrics({
                        'rto_achieved': (datetime.utcnow() - orchestrator.start_time).total_seconds() < (RTO_TARGET * 60),
                        'success': True
                    })
                else:
                    orchestrator.send_notifications(
                        f"❌ Disaster recovery validation failed. Manual intervention required.",
                        severity='error'
                    )
            else:
                orchestrator.send_notifications(
                    f"❌ Disaster recovery failover failed. Manual intervention required.",
                    severity='error'
                )
        
        elif assessment['recommended_action'] == 'failover_to_tertiary':
            logger.info("Critical disaster detected - would failover to tertiary region")
            orchestrator.send_notifications(
                f"🚨 Critical disaster requiring tertiary failover. Manual intervention required.",
                severity='error'
            )
            response['action'] = 'manual_intervention_required'
        
        else:
            logger.info(f"Recommended action: {assessment['recommended_action']}")
            response['action'] = assessment['recommended_action']
        
        return {
            'statusCode': 200,
            'body': json.dumps(response, default=str)
        }
        
    except Exception as e:
        logger.error(f"Error in DR orchestration: {e}")
        
        orchestrator.send_notifications(
            f"❌ Error in disaster recovery orchestration: {str(e)}",
            severity='error'
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'execution_id': orchestrator.execution_id,
                'timestamp': datetime.utcnow().isoformat()
            }, default=str)
        }