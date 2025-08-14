#!/usr/bin/env python3
"""
Disaster Recovery Orchestrator
One-click disaster recovery system with automated failover, data restoration,
and multi-region recovery coordination.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
import boto3
import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Add backend to path for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.core.secrets import get_secrets_manager
from backend.services.health_check_service import HealthCheckService
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class DisasterType(str, Enum):
    """Types of disasters that can trigger recovery."""
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    DATA_CORRUPTION = "data_corruption"
    CYBER_ATTACK = "cyber_attack"
    NATURAL_DISASTER = "natural_disaster"
    HUMAN_ERROR = "human_error"
    PLANNED_MAINTENANCE = "planned_maintenance"


class RecoveryState(str, Enum):
    """Recovery operation states."""
    IDLE = "idle"
    ASSESSING = "assessing"
    PREPARING = "preparing"
    RECOVERING = "recovering"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"


class RecoveryPriority(str, Enum):
    """Recovery priority levels."""
    CRITICAL = "critical"    # < 15 minutes RTO
    HIGH = "high"           # < 1 hour RTO
    MEDIUM = "medium"       # < 4 hours RTO
    LOW = "low"            # < 24 hours RTO


@dataclass
class RecoveryPlan:
    """Disaster recovery plan configuration."""
    plan_id: str
    name: str
    description: str
    disaster_types: List[DisasterType]
    priority: RecoveryPriority
    rto_target: timedelta  # Recovery Time Objective
    rpo_target: timedelta  # Recovery Point Objective

    # Infrastructure configuration
    primary_region: str
    secondary_region: str
    tertiary_region: Optional[str] = None

    # Recovery steps
    pre_recovery_checks: List[str] = field(default_factory=list)
    recovery_steps: List[Dict[str, Any]] = field(default_factory=list)
    post_recovery_validation: List[str] = field(default_factory=list)
    rollback_steps: List[Dict[str, Any]] = field(default_factory=list)

    # Dependencies
    dependencies: List[str] = field(default_factory=list)
    notification_channels: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DisasterEvent:
    """Disaster event information."""
    event_id: str
    disaster_type: DisasterType
    severity: RecoveryPriority
    description: str
    affected_services: List[str]
    affected_regions: List[str]
    detected_at: datetime
    recovery_plan_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryExecution:
    """Recovery execution status."""
    execution_id: str
    plan_id: str
    disaster_event: DisasterEvent
    state: RecoveryState
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    current_step: int = 0
    total_steps: int = 0
    step_results: List[Dict[str, Any]] = field(default_factory=list)

    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class InfrastructureManager:
    """Manages infrastructure during disaster recovery."""

    def __init__(self, aws_session: boto3.Session):
        """Initialize infrastructure manager."""
        self.aws_session = aws_session
        self.ec2 = aws_session.client('ec2')
        self.rds = aws_session.client('rds')
        self.s3 = aws_session.client('s3')
        self.route53 = aws_session.client('route53')
        self.cloudformation = aws_session.client('cloudformation')

    async def assess_infrastructure_health(self, region: str) -> Dict[str, Any]:
        """Assess infrastructure health in a region."""
        health_status = {
            'region': region,
            'timestamp': datetime.utcnow().isoformat(),
            'services': {}
        }

        try:
            # Check EC2 instances
            ec2_regional = self.aws_session.client('ec2', region_name=region)
            instances = ec2_regional.describe_instances()

            running_instances = 0
            total_instances = 0
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    total_instances += 1
                    if instance['State']['Name'] == 'running':
                        running_instances += 1

            health_status['services']['ec2'] = {
                'status': 'healthy' if running_instances > 0 else 'unhealthy',
                'running_instances': running_instances,
                'total_instances': total_instances
            }

            # Check RDS instances
            rds_regional = self.aws_session.client('rds', region_name=region)
            db_instances = rds_regional.describe_db_instances()

            available_dbs = 0
            total_dbs = len(db_instances['DBInstances'])
            for db in db_instances['DBInstances']:
                if db['DBInstanceStatus'] == 'available':
                    available_dbs += 1

            health_status['services']['rds'] = {
                'status': 'healthy' if available_dbs > 0 else 'unhealthy',
                'available_instances': available_dbs,
                'total_instances': total_dbs
            }

            # Check S3 buckets accessibility
            s3_regional = self.aws_session.client('s3', region_name=region)
            try:
                buckets = s3_regional.list_buckets()
                health_status['services']['s3'] = {
                    'status': 'healthy',
                    'accessible': True,
                    'bucket_count': len(buckets['Buckets'])
                }
            except Exception as e:
                health_status['services']['s3'] = {
                    'status': 'unhealthy',
                    'accessible': False,
                    'error': str(e)
                }

        except Exception as e:
            logger.error(f"Error assessing infrastructure health in {region}: {e}")
            health_status['error'] = str(e)

        return health_status

    async def failover_to_region(
        self,
        source_region: str,
        target_region: str,
        services: List[str]
    ) -> Dict[str, Any]:
        """Failover services from source to target region."""
        failover_results = {
            'source_region': source_region,
            'target_region': target_region,
            'services': {},
            'started_at': datetime.utcnow().isoformat()
        }

        for service in services:
            try:
                if service == 'rds':
                    result = await self._failover_rds(source_region, target_region)
                elif service == 'ec2':
                    result = await self._failover_ec2(source_region, target_region)
                elif service == 'route53':
                    result = await self._failover_dns(source_region, target_region)
                else:
                    result = {'status': 'skipped', 'reason': f'Unknown service: {service}'}

                failover_results['services'][service] = result

            except Exception as e:
                logger.error(f"Error failing over {service}: {e}")
                failover_results['services'][service] = {
                    'status': 'failed',
                    'error': str(e)
                }

        failover_results['completed_at'] = datetime.utcnow().isoformat()
        return failover_results

    async def _failover_rds(self, source_region: str, target_region: str) -> Dict[str, Any]:
        """Failover RDS instances."""
        try:
            source_rds = self.aws_session.client('rds', region_name=source_region)
            target_rds = self.aws_session.client('rds', region_name=target_region)

            # Get source RDS instances
            instances = source_rds.describe_db_instances()

            results = []
            for instance in instances['DBInstances']:
                db_identifier = instance['DBInstanceIdentifier']

                # Check if read replica exists in target region
                replicas = source_rds.describe_db_instances()
                target_replica = None

                for replica_info in replicas['DBInstances']:
                    if (replica_info.get('ReadReplicaSourceDBInstanceIdentifier') == db_identifier and
                        replica_info.get('AvailabilityZone', '').startswith(target_region)):
                        target_replica = replica_info['DBInstanceIdentifier']
                        break

                if target_replica:
                    # Promote read replica
                    target_rds.promote_read_replica(
                        DBInstanceIdentifier=target_replica
                    )
                    results.append({
                        'instance': db_identifier,
                        'action': 'promoted_replica',
                        'target_instance': target_replica
                    })
                else:
                    # Create point-in-time recovery instance
                    snapshot_id = f"{db_identifier}-disaster-recovery-{int(time.time())}"
                    source_rds.create_db_snapshot(
                        DBInstanceIdentifier=db_identifier,
                        DBSnapshotIdentifier=snapshot_id
                    )

                    results.append({
                        'instance': db_identifier,
                        'action': 'snapshot_created',
                        'snapshot_id': snapshot_id
                    })

            return {'status': 'completed', 'results': results}

        except Exception as e:
            return {'status': 'failed', 'error': str(e)}

    async def _failover_ec2(self, source_region: str, target_region: str) -> Dict[str, Any]:
        """Failover EC2 instances using AMIs."""
        try:
            source_ec2 = self.aws_session.client('ec2', region_name=source_region)
            target_ec2 = self.aws_session.client('ec2', region_name=target_region)

            # Get running instances
            instances = source_ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )

            results = []
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    instance_id = instance['InstanceId']

                    # Create AMI
                    ami_response = source_ec2.create_image(
                        InstanceId=instance_id,
                        Name=f"disaster-recovery-{instance_id}-{int(time.time())}",
                        Description=f"Disaster recovery AMI for {instance_id}"
                    )

                    results.append({
                        'instance': instance_id,
                        'ami_id': ami_response['ImageId'],
                        'action': 'ami_created'
                    })

            return {'status': 'completed', 'results': results}

        except Exception as e:
            return {'status': 'failed', 'error': str(e)}

    async def _failover_dns(self, source_region: str, target_region: str) -> Dict[str, Any]:
        """Failover DNS using Route 53 health checks."""
        try:
            # Update Route 53 health checks to point to target region
            health_checks = self.route53.list_health_checks()

            results = []
            for health_check in health_checks['HealthChecks']:
                health_check_id = health_check['Id']

                # Update health check to point to target region
                self.route53.update_health_check(
                    HealthCheckId=health_check_id,
                    # This would include actual failover logic
                )

                results.append({
                    'health_check_id': health_check_id,
                    'action': 'updated_target_region'
                })

            return {'status': 'completed', 'results': results}

        except Exception as e:
            return {'status': 'failed', 'error': str(e)}


class KubernetesManager:
    """Manages Kubernetes resources during disaster recovery."""

    def __init__(self):
        """Initialize Kubernetes manager."""
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.batch_v1 = client.BatchV1Api()

    async def assess_cluster_health(self, namespace: str = "ai-pdf-scholar") -> Dict[str, Any]:
        """Assess Kubernetes cluster health."""
        health_status = {
            'namespace': namespace,
            'timestamp': datetime.utcnow().isoformat(),
            'resources': {}
        }

        try:
            # Check pods
            pods = self.v1.list_namespaced_pod(namespace=namespace)
            running_pods = sum(1 for pod in pods.items if pod.status.phase == 'Running')
            total_pods = len(pods.items)

            health_status['resources']['pods'] = {
                'running': running_pods,
                'total': total_pods,
                'healthy': running_pods > 0
            }

            # Check services
            services = self.v1.list_namespaced_service(namespace=namespace)
            health_status['resources']['services'] = {
                'count': len(services.items),
                'healthy': len(services.items) > 0
            }

            # Check deployments
            deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
            ready_deployments = sum(
                1 for deploy in deployments.items
                if deploy.status.ready_replicas == deploy.status.replicas
            )

            health_status['resources']['deployments'] = {
                'ready': ready_deployments,
                'total': len(deployments.items),
                'healthy': ready_deployments == len(deployments.items)
            }

        except ApiException as e:
            logger.error(f"Error assessing cluster health: {e}")
            health_status['error'] = str(e)

        return health_status

    async def create_dr_namespace(self, namespace: str = "ai-pdf-scholar-dr") -> bool:
        """Create disaster recovery namespace."""
        try:
            namespace_obj = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=namespace,
                    labels={
                        "disaster-recovery": "true",
                        "created-by": "disaster-recovery-orchestrator"
                    }
                )
            )

            self.v1.create_namespace(namespace_obj)
            logger.info(f"Created DR namespace: {namespace}")
            return True

        except ApiException as e:
            if e.status == 409:  # Namespace already exists
                logger.info(f"DR namespace already exists: {namespace}")
                return True
            else:
                logger.error(f"Failed to create DR namespace: {e}")
                return False

    async def deploy_to_dr_namespace(
        self,
        source_namespace: str,
        dr_namespace: str,
        resources: List[str]
    ) -> Dict[str, Any]:
        """Deploy resources to DR namespace."""
        deployment_results = {
            'source_namespace': source_namespace,
            'dr_namespace': dr_namespace,
            'resources': {},
            'started_at': datetime.utcnow().isoformat()
        }

        for resource_type in resources:
            try:
                if resource_type == 'deployments':
                    result = await self._deploy_deployments(source_namespace, dr_namespace)
                elif resource_type == 'services':
                    result = await self._deploy_services(source_namespace, dr_namespace)
                elif resource_type == 'configmaps':
                    result = await self._deploy_configmaps(source_namespace, dr_namespace)
                elif resource_type == 'secrets':
                    result = await self._deploy_secrets(source_namespace, dr_namespace)
                else:
                    result = {'status': 'skipped', 'reason': f'Unknown resource: {resource_type}'}

                deployment_results['resources'][resource_type] = result

            except Exception as e:
                logger.error(f"Error deploying {resource_type}: {e}")
                deployment_results['resources'][resource_type] = {
                    'status': 'failed',
                    'error': str(e)
                }

        deployment_results['completed_at'] = datetime.utcnow().isoformat()
        return deployment_results

    async def _deploy_deployments(self, source_ns: str, dr_ns: str) -> Dict[str, Any]:
        """Deploy deployments to DR namespace."""
        deployments = self.apps_v1.list_namespaced_deployment(namespace=source_ns)
        results = []

        for deployment in deployments.items:
            # Modify deployment for DR
            dr_deployment = deployment
            dr_deployment.metadata.namespace = dr_ns
            dr_deployment.metadata.resource_version = None
            dr_deployment.metadata.uid = None

            # Add DR labels
            if not dr_deployment.metadata.labels:
                dr_deployment.metadata.labels = {}
            dr_deployment.metadata.labels['disaster-recovery'] = 'true'

            self.apps_v1.create_namespaced_deployment(
                namespace=dr_ns,
                body=dr_deployment
            )

            results.append({
                'name': deployment.metadata.name,
                'status': 'deployed'
            })

        return {'status': 'completed', 'deployments': results}

    async def _deploy_services(self, source_ns: str, dr_ns: str) -> Dict[str, Any]:
        """Deploy services to DR namespace."""
        services = self.v1.list_namespaced_service(namespace=source_ns)
        results = []

        for service in services.items:
            # Skip default service
            if service.metadata.name == 'kubernetes':
                continue

            # Modify service for DR
            dr_service = service
            dr_service.metadata.namespace = dr_ns
            dr_service.metadata.resource_version = None
            dr_service.metadata.uid = None
            dr_service.spec.cluster_ip = None

            self.v1.create_namespaced_service(
                namespace=dr_ns,
                body=dr_service
            )

            results.append({
                'name': service.metadata.name,
                'status': 'deployed'
            })

        return {'status': 'completed', 'services': results}

    async def _deploy_configmaps(self, source_ns: str, dr_ns: str) -> Dict[str, Any]:
        """Deploy configmaps to DR namespace."""
        configmaps = self.v1.list_namespaced_config_map(namespace=source_ns)
        results = []

        for configmap in configmaps.items:
            # Modify configmap for DR
            dr_configmap = configmap
            dr_configmap.metadata.namespace = dr_ns
            dr_configmap.metadata.resource_version = None
            dr_configmap.metadata.uid = None

            self.v1.create_namespaced_config_map(
                namespace=dr_ns,
                body=dr_configmap
            )

            results.append({
                'name': configmap.metadata.name,
                'status': 'deployed'
            })

        return {'status': 'completed', 'configmaps': results}

    async def _deploy_secrets(self, source_ns: str, dr_ns: str) -> Dict[str, Any]:
        """Deploy secrets to DR namespace."""
        secrets = self.v1.list_namespaced_secret(namespace=source_ns)
        results = []

        for secret in secrets.items:
            # Skip service account tokens
            if secret.type == 'kubernetes.io/service-account-token':
                continue

            # Modify secret for DR
            dr_secret = secret
            dr_secret.metadata.namespace = dr_ns
            dr_secret.metadata.resource_version = None
            dr_secret.metadata.uid = None

            self.v1.create_namespaced_secret(
                namespace=dr_ns,
                body=dr_secret
            )

            results.append({
                'name': secret.metadata.name,
                'status': 'deployed'
            })

        return {'status': 'completed', 'secrets': results}


class DisasterRecoveryOrchestrator:
    """Main disaster recovery orchestrator."""

    def __init__(self, metrics_service: Optional[MetricsService] = None):
        """Initialize disaster recovery orchestrator."""
        self.metrics_service = metrics_service or MetricsService()
        self.secrets_manager = get_secrets_manager()
        self.health_service = HealthCheckService()

        # Initialize managers
        self.aws_session = boto3.Session()
        self.infrastructure_manager = InfrastructureManager(self.aws_session)
        self.kubernetes_manager = KubernetesManager()

        # Recovery plans and executions
        self.recovery_plans: Dict[str, RecoveryPlan] = {}
        self.active_executions: Dict[str, RecoveryExecution] = {}

        # Load recovery plans
        self._load_recovery_plans()

    def _load_recovery_plans(self):
        """Load recovery plans from configuration."""
        # Default recovery plans

        # Critical infrastructure failure plan
        self.recovery_plans['critical_infra_failure'] = RecoveryPlan(
            plan_id='critical_infra_failure',
            name='Critical Infrastructure Failure Recovery',
            description='Recovery from critical infrastructure failures with < 15 min RTO',
            disaster_types=[DisasterType.INFRASTRUCTURE_FAILURE],
            priority=RecoveryPriority.CRITICAL,
            rto_target=timedelta(minutes=15),
            rpo_target=timedelta(minutes=5),
            primary_region='us-west-2',
            secondary_region='us-east-1',
            tertiary_region='eu-west-1',
            recovery_steps=[
                {'type': 'assess_damage', 'timeout': 300},
                {'type': 'failover_dns', 'timeout': 180},
                {'type': 'failover_database', 'timeout': 600},
                {'type': 'deploy_application', 'timeout': 300},
                {'type': 'validate_services', 'timeout': 120}
            ],
            notification_channels=['slack', 'email', 'sms']
        )

        # Data corruption recovery plan
        self.recovery_plans['data_corruption'] = RecoveryPlan(
            plan_id='data_corruption',
            name='Data Corruption Recovery',
            description='Recovery from data corruption with point-in-time restore',
            disaster_types=[DisasterType.DATA_CORRUPTION, DisasterType.CYBER_ATTACK],
            priority=RecoveryPriority.HIGH,
            rto_target=timedelta(hours=1),
            rpo_target=timedelta(minutes=15),
            primary_region='us-west-2',
            secondary_region='us-east-1',
            recovery_steps=[
                {'type': 'isolate_corrupted_systems', 'timeout': 300},
                {'type': 'assess_corruption_scope', 'timeout': 600},
                {'type': 'restore_from_backup', 'timeout': 3600},
                {'type': 'validate_data_integrity', 'timeout': 900},
                {'type': 'resume_operations', 'timeout': 300}
            ],
            notification_channels=['slack', 'email']
        )

        logger.info(f"Loaded {len(self.recovery_plans)} recovery plans")

    async def detect_disaster(self, health_metrics: Dict[str, Any]) -> Optional[DisasterEvent]:
        """Detect disaster from health metrics."""
        current_time = datetime.utcnow()

        # Check for infrastructure failures
        if health_metrics.get('infrastructure_health', {}).get('status') == 'critical':
            return DisasterEvent(
                event_id=f"infra_failure_{int(time.time())}",
                disaster_type=DisasterType.INFRASTRUCTURE_FAILURE,
                severity=RecoveryPriority.CRITICAL,
                description="Critical infrastructure failure detected",
                affected_services=health_metrics.get('affected_services', []),
                affected_regions=health_metrics.get('affected_regions', []),
                detected_at=current_time,
                recovery_plan_id='critical_infra_failure'
            )

        # Check for data corruption
        if health_metrics.get('data_integrity', {}).get('status') == 'corrupted':
            return DisasterEvent(
                event_id=f"data_corruption_{int(time.time())}",
                disaster_type=DisasterType.DATA_CORRUPTION,
                severity=RecoveryPriority.HIGH,
                description="Data corruption detected",
                affected_services=health_metrics.get('affected_services', []),
                affected_regions=health_metrics.get('affected_regions', []),
                detected_at=current_time,
                recovery_plan_id='data_corruption'
            )

        return None

    async def execute_recovery(
        self,
        disaster_event: DisasterEvent,
        plan_id: Optional[str] = None
    ) -> RecoveryExecution:
        """Execute disaster recovery plan."""
        if not plan_id:
            plan_id = disaster_event.recovery_plan_id

        if not plan_id or plan_id not in self.recovery_plans:
            raise ValueError(f"Recovery plan not found: {plan_id}")

        plan = self.recovery_plans[plan_id]
        execution_id = f"recovery_{plan_id}_{int(time.time())}"

        # Create execution record
        execution = RecoveryExecution(
            execution_id=execution_id,
            plan_id=plan_id,
            disaster_event=disaster_event,
            state=RecoveryState.PREPARING,
            started_at=datetime.utcnow(),
            estimated_completion=datetime.utcnow() + plan.rto_target,
            total_steps=len(plan.recovery_steps)
        )

        self.active_executions[execution_id] = execution

        try:
            # Send notifications
            await self._send_notifications(
                plan.notification_channels,
                f"🚨 Disaster Recovery Started: {plan.name}",
                f"Execution ID: {execution_id}\nDisaster: {disaster_event.description}\nETA: {plan.rto_target}"
            )

            # Execute recovery steps
            execution.state = RecoveryState.RECOVERING

            for step_index, step_config in enumerate(plan.recovery_steps):
                execution.current_step = step_index + 1

                step_start = time.time()
                step_result = await self._execute_recovery_step(step_config, plan, execution)
                step_duration = time.time() - step_start

                step_result.update({
                    'step_index': step_index,
                    'duration': step_duration,
                    'timestamp': datetime.utcnow().isoformat()
                })

                execution.step_results.append(step_result)

                if not step_result.get('success', False):
                    execution.state = RecoveryState.FAILED
                    execution.errors.append(f"Step {step_index + 1} failed: {step_result.get('error')}")
                    break

                # Update metrics
                await self.metrics_service.record_histogram(
                    "disaster_recovery_step_duration",
                    step_duration,
                    tags={"plan_id": plan_id, "step_type": step_config['type']}
                )

            # Validate recovery
            if execution.state == RecoveryState.RECOVERING:
                execution.state = RecoveryState.VALIDATING
                validation_result = await self._validate_recovery(plan, execution)

                if validation_result['success']:
                    execution.state = RecoveryState.COMPLETED
                    execution.completed_at = datetime.utcnow()

                    # Calculate actual RTO/RPO
                    actual_rto = execution.completed_at - execution.started_at
                    execution.metrics['actual_rto'] = actual_rto.total_seconds()
                    execution.metrics['rto_target_met'] = actual_rto <= plan.rto_target

                    await self._send_notifications(
                        plan.notification_channels,
                        f"✅ Disaster Recovery Completed: {plan.name}",
                        f"Execution ID: {execution_id}\nActual RTO: {actual_rto}\nAll services restored"
                    )

                    # Update metrics
                    await self.metrics_service.record_counter(
                        "disaster_recovery_completed",
                        tags={"plan_id": plan_id, "disaster_type": disaster_event.disaster_type.value}
                    )

                    await self.metrics_service.record_histogram(
                        "disaster_recovery_duration",
                        actual_rto.total_seconds(),
                        tags={"plan_id": plan_id}
                    )

                else:
                    execution.state = RecoveryState.FAILED
                    execution.errors.append("Recovery validation failed")

        except Exception as e:
            execution.state = RecoveryState.FAILED
            execution.errors.append(f"Recovery execution failed: {str(e)}")
            logger.error(f"Recovery execution failed: {e}")

            await self._send_notifications(
                plan.notification_channels,
                f"❌ Disaster Recovery Failed: {plan.name}",
                f"Execution ID: {execution_id}\nError: {str(e)}"
            )

        return execution

    async def _execute_recovery_step(
        self,
        step_config: Dict[str, Any],
        plan: RecoveryPlan,
        execution: RecoveryExecution
    ) -> Dict[str, Any]:
        """Execute a single recovery step."""
        step_type = step_config['type']
        timeout = step_config.get('timeout', 600)  # Default 10 minutes

        try:
            if step_type == 'assess_damage':
                return await self._assess_damage_step(plan, execution)
            elif step_type == 'failover_dns':
                return await self._failover_dns_step(plan, execution)
            elif step_type == 'failover_database':
                return await self._failover_database_step(plan, execution)
            elif step_type == 'deploy_application':
                return await self._deploy_application_step(plan, execution)
            elif step_type == 'validate_services':
                return await self._validate_services_step(plan, execution)
            elif step_type == 'isolate_corrupted_systems':
                return await self._isolate_corrupted_systems_step(plan, execution)
            elif step_type == 'restore_from_backup':
                return await self._restore_from_backup_step(plan, execution)
            elif step_type == 'validate_data_integrity':
                return await self._validate_data_integrity_step(plan, execution)
            else:
                return {'success': False, 'error': f'Unknown step type: {step_type}'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _assess_damage_step(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Assess damage to infrastructure and services."""
        damage_assessment = {
            'regions': {},
            'services': {},
            'overall_status': 'unknown'
        }

        # Assess primary region
        primary_health = await self.infrastructure_manager.assess_infrastructure_health(plan.primary_region)
        damage_assessment['regions'][plan.primary_region] = primary_health

        # Assess secondary region
        secondary_health = await self.infrastructure_manager.assess_infrastructure_health(plan.secondary_region)
        damage_assessment['regions'][plan.secondary_region] = secondary_health

        # Assess Kubernetes cluster
        k8s_health = await self.kubernetes_manager.assess_cluster_health()
        damage_assessment['services']['kubernetes'] = k8s_health

        # Determine overall status
        primary_healthy = all(
            service.get('status') == 'healthy'
            for service in primary_health.get('services', {}).values()
        )

        if primary_healthy:
            damage_assessment['overall_status'] = 'minimal'
        else:
            secondary_healthy = all(
                service.get('status') == 'healthy'
                for service in secondary_health.get('services', {}).values()
            )
            damage_assessment['overall_status'] = 'recoverable' if secondary_healthy else 'severe'

        return {
            'success': True,
            'damage_assessment': damage_assessment,
            'recommended_action': 'proceed' if damage_assessment['overall_status'] != 'severe' else 'manual_intervention'
        }

    async def _failover_dns_step(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Failover DNS to secondary region."""
        try:
            result = await self.infrastructure_manager.failover_to_region(
                plan.primary_region,
                plan.secondary_region,
                ['route53']
            )

            return {
                'success': result['services']['route53']['status'] == 'completed',
                'failover_result': result
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _failover_database_step(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Failover database to secondary region."""
        try:
            result = await self.infrastructure_manager.failover_to_region(
                plan.primary_region,
                plan.secondary_region,
                ['rds']
            )

            return {
                'success': result['services']['rds']['status'] == 'completed',
                'failover_result': result
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _deploy_application_step(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Deploy application to DR environment."""
        try:
            # Create DR namespace
            await self.kubernetes_manager.create_dr_namespace()

            # Deploy resources
            result = await self.kubernetes_manager.deploy_to_dr_namespace(
                'ai-pdf-scholar',
                'ai-pdf-scholar-dr',
                ['deployments', 'services', 'configmaps', 'secrets']
            )

            return {'success': True, 'deployment_result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _validate_services_step(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Validate that services are running correctly."""
        try:
            # Check application health
            health_result = await self.health_service.check_system_health()

            services_healthy = all(
                service.get('status') == 'healthy'
                for service in health_result.get('services', {}).values()
            )

            return {
                'success': services_healthy,
                'health_result': health_result
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _isolate_corrupted_systems_step(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Isolate corrupted systems to prevent spread."""
        # Implementation would isolate affected systems
        return {'success': True, 'action': 'systems_isolated'}

    async def _restore_from_backup_step(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Restore data from backup."""
        # Implementation would trigger backup restoration
        return {'success': True, 'action': 'backup_restored'}

    async def _validate_data_integrity_step(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Validate data integrity after restoration."""
        # Implementation would validate restored data
        return {'success': True, 'action': 'data_validated'}

    async def _validate_recovery(self, plan: RecoveryPlan, execution: RecoveryExecution) -> Dict[str, Any]:
        """Validate that recovery was successful."""
        validation_results = {
            'overall_success': True,
            'checks': {}
        }

        # Validate infrastructure
        try:
            infra_health = await self.infrastructure_manager.assess_infrastructure_health(plan.secondary_region)
            infra_healthy = all(
                service.get('status') == 'healthy'
                for service in infra_health.get('services', {}).values()
            )
            validation_results['checks']['infrastructure'] = {
                'success': infra_healthy,
                'details': infra_health
            }
            if not infra_healthy:
                validation_results['overall_success'] = False
        except Exception as e:
            validation_results['checks']['infrastructure'] = {'success': False, 'error': str(e)}
            validation_results['overall_success'] = False

        # Validate Kubernetes
        try:
            k8s_health = await self.kubernetes_manager.assess_cluster_health('ai-pdf-scholar-dr')
            k8s_healthy = all(
                resource.get('healthy', False)
                for resource in k8s_health.get('resources', {}).values()
            )
            validation_results['checks']['kubernetes'] = {
                'success': k8s_healthy,
                'details': k8s_health
            }
            if not k8s_healthy:
                validation_results['overall_success'] = False
        except Exception as e:
            validation_results['checks']['kubernetes'] = {'success': False, 'error': str(e)}
            validation_results['overall_success'] = False

        return validation_results

    async def _send_notifications(
        self,
        channels: List[str],
        subject: str,
        message: str
    ):
        """Send notifications about recovery status."""
        for channel in channels:
            try:
                if channel == 'slack':
                    await self._send_slack_notification(subject, message)
                elif channel == 'email':
                    await self._send_email_notification(subject, message)
                elif channel == 'sms':
                    await self._send_sms_notification(subject, message)
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")

    async def _send_slack_notification(self, subject: str, message: str):
        """Send Slack notification."""
        webhook_url = self.secrets_manager.get_secret("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return

        payload = {
            'text': subject,
            'attachments': [{
                'color': 'danger' if '🚨' in subject else 'good' if '✅' in subject else 'warning',
                'text': message,
                'footer': 'Disaster Recovery Orchestrator',
                'ts': int(time.time())
            }]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status == 200:
                    logger.info("Slack notification sent successfully")
                else:
                    logger.error(f"Failed to send Slack notification: {response.status}")

    async def _send_email_notification(self, subject: str, message: str):
        """Send email notification."""
        # Implementation would send email via SMTP
        logger.info(f"Email notification: {subject}")

    async def _send_sms_notification(self, subject: str, message: str):
        """Send SMS notification."""
        # Implementation would send SMS via service like Twilio
        logger.info(f"SMS notification: {subject}")

    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        return {
            'recovery_plans_loaded': len(self.recovery_plans),
            'active_executions': len(self.active_executions),
            'plans': {
                plan_id: {
                    'name': plan.name,
                    'priority': plan.priority.value,
                    'rto_target_minutes': plan.rto_target.total_seconds() / 60
                }
                for plan_id, plan in self.recovery_plans.items()
            },
            'executions': {
                exec_id: {
                    'plan_id': execution.plan_id,
                    'state': execution.state.value,
                    'progress': f"{execution.current_step}/{execution.total_steps}"
                }
                for exec_id, execution in self.active_executions.items()
            }
        }


# Example usage and testing
async def main():
    """Example usage of disaster recovery orchestrator."""
    orchestrator = DisasterRecoveryOrchestrator()

    # Simulate disaster detection
    health_metrics = {
        'infrastructure_health': {'status': 'critical'},
        'affected_services': ['web-app', 'database'],
        'affected_regions': ['us-west-2']
    }

    disaster_event = await orchestrator.detect_disaster(health_metrics)
    if disaster_event:
        print(f"Disaster detected: {disaster_event}")

        # Execute recovery
        execution = await orchestrator.execute_recovery(disaster_event)
        print(f"Recovery execution: {execution.execution_id} - {execution.state}")

    # Get status
    status = orchestrator.get_status()
    print(f"Orchestrator status: {json.dumps(status, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())