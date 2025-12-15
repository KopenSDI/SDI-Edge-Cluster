#!/usr/bin/env python3
"""
SDI Migration Service
MALE 기반 정책 엔진 및 클러스터 가용 자원 기반 마이그레이션 서비스
"""

import os
import time
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClusterResourceMonitor:
    """클러스터 리소스 모니터링 클래스"""
    
    def __init__(self, k8s_client):
        self.k8s_client = k8s_client
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
    
    def get_node_resources(self, node_name: str) -> Dict:
        """노드의 리소스 사용량 조회"""
        try:
            node = self.v1.read_node(name=node_name)
            status = node.status
            
            # CPU 및 Memory 사용량 계산
            allocatable = status.allocatable
            capacity = status.capacity
            
            cpu_allocatable = self._parse_resource(allocatable.get('cpu', '0'))
            memory_allocatable = self._parse_resource(allocatable.get('memory', '0'))
            cpu_capacity = self._parse_resource(capacity.get('cpu', '0'))
            memory_capacity = self._parse_resource(capacity.get('memory', '0'))
            
            # Pod 리소스 사용량 집계
            pods = self.v1.list_pod_for_all_namespaces(field_selector=f'spec.nodeName={node_name}')
            cpu_used = 0
            memory_used = 0
            
            for pod in pods.items:
                for container in pod.spec.containers:
                    if container.resources and container.resources.requests:
                        cpu_used += self._parse_resource(container.resources.requests.get('cpu', '0'))
                        memory_used += self._parse_resource(container.resources.requests.get('memory', '0'))
            
            cpu_usage_percent = (cpu_used / cpu_capacity * 100) if cpu_capacity > 0 else 0
            memory_usage_percent = (memory_used / memory_capacity * 100) if memory_capacity > 0 else 0
            
            return {
                'node_name': node_name,
                'cpu_usage_percent': cpu_usage_percent,
                'memory_usage_percent': memory_usage_percent,
                'cpu_allocatable': cpu_allocatable,
                'memory_allocatable': memory_allocatable,
                'cpu_used': cpu_used,
                'memory_used': memory_used,
                'pod_count': len(pods.items)
            }
        except ApiException as e:
            logger.error(f"Failed to get node resources for {node_name}: {e}")
            return None
    
    def _parse_resource(self, resource_str: str) -> float:
        """리소스 문자열을 숫자로 변환 (예: '100m' -> 0.1, '1Gi' -> 1024)"""
        if not resource_str:
            return 0.0
        
        resource_str = str(resource_str).strip()
        
        # CPU 처리 (cores 또는 millicores)
        if resource_str.endswith('m'):
            return float(resource_str[:-1]) / 1000.0
        elif resource_str.replace('.', '').isdigit():
            return float(resource_str)
        
        # Memory 처리 (Ki, Mi, Gi, Ti)
        multipliers = {'Ki': 1024, 'Mi': 1024**2, 'Gi': 1024**3, 'Ti': 1024**4}
        for unit, multiplier in multipliers.items():
            if resource_str.endswith(unit):
                return float(resource_str[:-len(unit)]) * multiplier
        
        return 0.0
    
    def get_all_nodes_resources(self) -> List[Dict]:
        """모든 노드의 리소스 사용량 조회"""
        nodes = self.v1.list_node()
        node_resources = []
        
        for node in nodes.items:
            # Skip control-plane nodes for migration targets
            if 'node-role.kubernetes.io/control-plane' in node.metadata.labels:
                continue
            
            resources = self.get_node_resources(node.metadata.name)
            if resources:
                node_resources.append(resources)
        
        return node_resources
    
    def get_pod_info(self, pod_name: str, namespace: str = "default") -> Optional[Dict]:
        """Pod 정보 조회"""
        try:
            pod = self.v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            return {
                'name': pod.metadata.name,
                'namespace': pod.metadata.namespace,
                'node_name': pod.spec.node_name,
                'labels': pod.metadata.labels,
                'status': pod.status.phase,
                'containers': [c.name for c in pod.spec.containers]
            }
        except ApiException as e:
            logger.error(f"Failed to get pod info for {pod_name}: {e}")
            return None


class PolicyEngineClient:
    """정책 엔진 클라이언트"""
    
    def __init__(self, policy_engine_url: str):
        self.base_url = policy_engine_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 5
    
    def get_migration_policy(self, pod_info: Dict, source_node: str, target_node: str) -> Optional[Dict]:
        """정책 엔진에서 마이그레이션 정책 조회"""
        try:
            url = f"{self.base_url}/api/v1/migration/policy"
            payload = {
                'pod': pod_info,
                'source_node': source_node,
                'target_node': target_node
            }
            response = self.session.post(url, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to get migration policy from policy engine: {e}")
            return None
    
    def should_migrate(self, pod_info: Dict, node_resources: Dict, threshold: float) -> bool:
        """마이그레이션 필요 여부 판단"""
        # 리소스 압박도 체크
        if node_resources['cpu_usage_percent'] > threshold:
            logger.info(f"Node {node_resources['node_name']} CPU usage {node_resources['cpu_usage_percent']:.2f}% exceeds threshold {threshold}%")
            return True
        
        if node_resources['memory_usage_percent'] > threshold:
            logger.info(f"Node {node_resources['node_name']} Memory usage {node_resources['memory_usage_percent']:.2f}% exceeds threshold {threshold}%")
            return True
        
        return False


class CheckpointManager:
    """체크포인팅 및 상태 전송 관리자"""
    
    def __init__(self, k8s_client, enable_checkpointing: bool = True):
        self.k8s_client = k8s_client
        self.v1 = client.CoreV1Api()
        self.enable_checkpointing = enable_checkpointing
    
    def create_checkpoint(self, pod_name: str, namespace: str = "default") -> Optional[str]:
        """Pod의 체크포인트 생성"""
        if not self.enable_checkpointing:
            logger.info("Checkpointing is disabled, skipping checkpoint creation")
            return None
        
        try:
            # 실제 구현에서는 CRI-O 또는 containerd의 checkpoint 기능 사용
            # 여기서는 시뮬레이션으로 처리
            checkpoint_id = f"checkpoint-{pod_name}-{int(time.time())}"
            logger.info(f"Creating checkpoint {checkpoint_id} for pod {pod_name}")
            
            # TODO: 실제 체크포인트 생성 로직 구현
            # 예: kubectl checkpoint create <pod> --checkpoint-dir=/tmp/checkpoints
            
            return checkpoint_id
        except Exception as e:
            logger.error(f"Failed to create checkpoint for {pod_name}: {e}")
            return None
    
    def restore_checkpoint(self, checkpoint_id: str, target_node: str, namespace: str = "default") -> bool:
        """체크포인트에서 복원"""
        if not self.enable_checkpointing:
            return True
        
        try:
            logger.info(f"Restoring checkpoint {checkpoint_id} on node {target_node}")
            # TODO: 실제 체크포인트 복원 로직 구현
            return True
        except Exception as e:
            logger.error(f"Failed to restore checkpoint {checkpoint_id}: {e}")
            return False


class MigrationService:
    """마이그레이션 서비스 메인 클래스"""
    
    def __init__(self):
        # Kubernetes 클라이언트 초기화
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        self.k8s_client = client.ApiClient()
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        
        # 환경 변수
        self.influx_url = os.getenv('INFLUX_URL', 'http://influxdb.tbot-monitoring.svc.cluster.local:8086')
        self.influx_org = os.getenv('INFLUX_ORG', 'keti')
        self.influx_bucket = os.getenv('INFLUX_BUCKET', 'turtlebot')
        self.influx_token = os.getenv('INFLUX_TOKEN', '')
        self.policy_engine_url = os.getenv('POLICY_ENGINE_URL', 'http://policy-engine.orchestration-engines.svc.cluster.local:8080')
        self.check_interval = int(os.getenv('MIGRATION_CHECK_INTERVAL', '30'))
        self.resource_threshold = float(os.getenv('RESOURCE_PRESSURE_THRESHOLD', '85'))
        self.enable_checkpointing = os.getenv('ENABLE_CHECKPOINTING', 'true').lower() == 'true'
        
        # 컴포넌트 초기화
        self.resource_monitor = ClusterResourceMonitor(self.k8s_client)
        self.policy_client = PolicyEngineClient(self.policy_engine_url)
        self.checkpoint_manager = CheckpointManager(self.k8s_client, self.enable_checkpointing)
        
        # InfluxDB 클라이언트
        if self.influx_token:
            self.influx_client = InfluxDBClient(
                url=self.influx_url,
                token=self.influx_token,
                org=self.influx_org
            )
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        else:
            self.influx_client = None
            self.write_api = None
            logger.warning("InfluxDB token not provided, metrics will not be written")
    
    def find_target_node(self, source_node: str, required_cpu: float = 0.0, required_memory: float = 0.0) -> Optional[str]:
        """마이그레이션 대상 노드 찾기"""
        nodes = self.resource_monitor.get_all_nodes_resources()
        
        best_node = None
        best_score = -1
        
        for node in nodes:
            if node['node_name'] == source_node:
                continue
            
            # 리소스 여유도 계산
            cpu_available = node['cpu_allocatable'] - node['cpu_used']
            memory_available = node['memory_allocatable'] - node['memory_used']
            
            # 요구사항 충족 여부 확인
            if cpu_available < required_cpu or memory_available < required_memory:
                continue
            
            # 스코어 계산 (리소스 여유도 기반)
            cpu_score = (cpu_available / node['cpu_allocatable']) * 100 if node['cpu_allocatable'] > 0 else 0
            memory_score = (memory_available / node['memory_allocatable']) * 100 if node['memory_allocatable'] > 0 else 0
            score = (cpu_score + memory_score) / 2
            
            if score > best_score:
                best_score = score
                best_node = node['node_name']
        
        return best_node
    
    def migrate_pod(self, pod_name: str, namespace: str = "default", target_node: Optional[str] = None) -> bool:
        """Pod 마이그레이션 수행"""
        try:
            pod_info = self.resource_monitor.get_pod_info(pod_name, namespace)
            if not pod_info:
                logger.error(f"Pod {pod_name} not found")
                return False
            
            source_node = pod_info['node_name']
            
            # Deployment 기반 Pod인지 확인
            deployment_name = None
            if pod_info['labels']:
                for key, value in pod_info['labels'].items():
                    if 'deployment' in key.lower() or 'app' in key.lower():
                        # Deployment 이름 추정
                        deployment_name = value
                        break
            
            # 대상 노드가 지정되지 않은 경우 자동 선택
            if not target_node:
                # Pod 리소스 요구사항 계산
                pod = self.v1.read_namespaced_pod(name=pod_name, namespace=namespace)
                required_cpu = 0.0
                required_memory = 0.0
                
                for container in pod.spec.containers:
                    if container.resources and container.resources.requests:
                        required_cpu += self.resource_monitor._parse_resource(
                            container.resources.requests.get('cpu', '0')
                        )
                        required_memory += self.resource_monitor._parse_resource(
                            container.resources.requests.get('memory', '0')
                        )
                
                target_node = self.find_target_node(source_node, required_cpu, required_memory)
            
            if not target_node:
                logger.error(f"No suitable target node found for pod {pod_name}")
                return False
            
            logger.info(f"Migrating pod {pod_name} from {source_node} to {target_node}")
            
            # 정책 엔진 확인
            policy = self.policy_client.get_migration_policy(pod_info, source_node, target_node)
            if policy and not policy.get('allowed', True):
                logger.warning(f"Migration not allowed by policy engine: {policy.get('reason', 'Unknown')}")
                return False
            
            # 체크포인트 생성
            checkpoint_id = self.checkpoint_manager.create_checkpoint(pod_name, namespace)
            
            # Deployment 기반 마이그레이션
            if deployment_name:
                try:
                    deployment = self.apps_v1.read_namespaced_deployment(
                        name=deployment_name,
                        namespace=namespace
                    )
                    
                    # nodeSelector 업데이트
                    if not deployment.spec.template.spec.node_selector:
                        deployment.spec.template.spec.node_selector = {}
                    
                    deployment.spec.template.spec.node_selector['kubernetes.io/hostname'] = target_node
                    
                    # Deployment 업데이트
                    self.apps_v1.patch_namespaced_deployment(
                        name=deployment_name,
                        namespace=namespace,
                        body=deployment
                    )
                    
                    logger.info(f"Updated deployment {deployment_name} to migrate to {target_node}")
                    
                    # 롤아웃 완료 대기
                    self._wait_for_rollout(deployment_name, namespace)
                    
                    # 체크포인트 복원 (필요시)
                    if checkpoint_id:
                        self.checkpoint_manager.restore_checkpoint(checkpoint_id, target_node, namespace)
                    
                    # 마이그레이션 메트릭 기록
                    self._record_migration_metric(pod_name, source_node, target_node, True)
                    
                    return True
                except ApiException as e:
                    logger.error(f"Failed to migrate deployment {deployment_name}: {e}")
                    return False
            else:
                # 단일 Pod 마이그레이션 (Eviction 사용)
                try:
                    eviction = client.V1Eviction(
                        metadata=client.V1ObjectMeta(name=pod_name, namespace=namespace)
                    )
                    self.v1.create_namespaced_pod_eviction(
                        name=pod_name,
                        namespace=namespace,
                        body=eviction
                    )
                    
                    logger.info(f"Evicted pod {pod_name}, waiting for reschedule")
                    # Pod가 재스케줄링될 때까지 대기
                    time.sleep(5)
                    
                    self._record_migration_metric(pod_name, source_node, target_node, True)
                    return True
                except ApiException as e:
                    logger.error(f"Failed to evict pod {pod_name}: {e}")
                    return False
        
        except Exception as e:
            logger.error(f"Migration failed for pod {pod_name}: {e}")
            self._record_migration_metric(pod_name, source_node if 'source_node' in locals() else 'unknown', 
                                        target_node if 'target_node' in locals() else 'unknown', False)
            return False
    
    def _wait_for_rollout(self, deployment_name: str, namespace: str, timeout: int = 300):
        """Deployment 롤아웃 완료 대기"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                deployment = self.apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=namespace
                )
                
                if (deployment.status.updated_replicas == deployment.spec.replicas and
                    deployment.status.ready_replicas == deployment.spec.replicas):
                    logger.info(f"Deployment {deployment_name} rollout completed")
                    return True
                
                time.sleep(2)
            except ApiException as e:
                logger.error(f"Error waiting for rollout: {e}")
                return False
        
        logger.warning(f"Deployment {deployment_name} rollout timeout")
        return False
    
    def _record_migration_metric(self, pod_name: str, source_node: str, target_node: str, success: bool):
        """마이그레이션 메트릭을 InfluxDB에 기록"""
        if not self.write_api:
            return
        
        try:
            point = Point("pod_migration") \
                .tag("pod_name", pod_name) \
                .tag("source_node", source_node) \
                .tag("target_node", target_node) \
                .tag("success", str(success)) \
                .field("migration_count", 1) \
                .time(time.time_ns())
            
            self.write_api.write(bucket=self.influx_bucket, org=self.influx_org, record=point)
        except Exception as e:
            logger.error(f"Failed to record migration metric: {e}")
    
    def monitor_and_migrate(self):
        """주기적으로 모니터링하고 마이그레이션 수행"""
        logger.info("Starting migration service monitoring loop")
        
        while True:
            try:
                # 모든 노드 리소스 확인
                nodes = self.resource_monitor.get_all_nodes_resources()
                
                for node in nodes:
                    # 리소스 압박도 체크
                    if self.policy_client.should_migrate({}, node, self.resource_threshold):
                        logger.info(f"Resource pressure detected on node {node['node_name']}")
                        
                        # 해당 노드의 Pod들 조회
                        node_name = node['node_name']
                        pods = self.v1.list_pod_for_all_namespaces(
                            field_selector=f'spec.nodeName={node_name}'
                        )
                        
                        # 마이그레이션 대상 Pod 선택 (우선순위 기반)
                        migration_candidates = []
                        for pod in pods.items:
                            # 시스템 Pod 제외
                            if pod.metadata.namespace == 'kube-system':
                                continue
                            
                            # 정지 중이거나 실패한 Pod 제외
                            if pod.status.phase not in ['Running', 'Pending']:
                                continue
                            
                            migration_candidates.append(pod)
                        
                        # 우선순위에 따라 마이그레이션 수행
                        for pod in migration_candidates[:3]:  # 최대 3개까지
                            self.migrate_pod(pod.metadata.name, pod.metadata.namespace)
                            time.sleep(5)  # 마이그레이션 간 간격
                
                time.sleep(self.check_interval)
            
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)


def main():
    """메인 함수"""
    service = MigrationService()
    service.monitor_and_migrate()


if __name__ == '__main__':
    main()

