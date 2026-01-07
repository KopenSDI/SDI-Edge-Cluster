"""
Metric Federation Agent for Edge Cluster
=========================================
Edge Cluster에서 수집된 메트릭을 Central Cluster로 전송하는 에이전트

지원 디바이스 타입:
- SDR (Robot): TurtleBot, AMR 등
- SDA (Air): 드론, UAV 등
- SDV (Vehicle): AGV, 자율주행차 등
- UNKNOWN: 미분류 디바이스

전송 메트릭:
1. 클러스터 메트릭 (노드 상태, 리소스 사용량)
2. 워크로드 메트릭 (Pod, Deployment 상태)
3. 디바이스 메트릭 (범용 스키마)
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from kubernetes import client, config
from influxdb_client import InfluxDBClient

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# 환경 변수 설정
# ============================================================

# Edge Cluster 식별자
CLUSTER_ID = os.getenv('CLUSTER_ID', 'edge-cluster-01')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'KETI-Edge-Cluster')

# Central Cluster 연결 정보
CENTRAL_API_URL = os.getenv('CENTRAL_API_URL', 'http://10.0.5.55:30080')
CENTRAL_API_TOKEN = os.getenv('CENTRAL_API_TOKEN', '')

# InfluxDB 연결 정보 (디바이스 메트릭용)
INFLUX_URL = os.getenv('INFLUX_URL', 'http://influxdb.tbot-monitoring.svc.cluster.local:8086')
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN', '')
INFLUX_ORG = os.getenv('INFLUX_ORG', 'keti')
INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', 'turtlebot')

# 전송 주기 (초)
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', '30'))

# 재시도 설정
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))


# ============================================================
# Kubernetes 클라이언트 초기화
# ============================================================

def init_k8s_client():
    """Kubernetes 클라이언트 초기화 (클러스터 내부/외부 자동 감지)"""
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config")
    except config.ConfigException:
        config.load_kube_config()
        logger.info("Loaded local kubeconfig")

    return client.CoreV1Api(), client.AppsV1Api()


# ============================================================
# 클러스터 메트릭 수집
# ============================================================

def collect_cluster_metrics(v1: client.CoreV1Api) -> Dict[str, Any]:
    """클러스터 레벨 메트릭 수집 (노드 상태, 리소스)"""

    nodes_info = []
    total_cpu_capacity = 0
    total_memory_capacity = 0
    total_cpu_allocatable = 0
    total_memory_allocatable = 0

    try:
        nodes = v1.list_node()

        for node in nodes.items:
            node_name = node.metadata.name
            labels = node.metadata.labels or {}

            # 노드 상태 확인
            conditions = {c.type: c.status for c in node.status.conditions}
            is_ready = conditions.get('Ready', 'Unknown') == 'True'

            # 리소스 용량
            capacity = node.status.capacity or {}
            allocatable = node.status.allocatable or {}

            cpu_capacity = parse_cpu(capacity.get('cpu', '0'))
            memory_capacity = parse_memory(capacity.get('memory', '0'))
            cpu_allocatable = parse_cpu(allocatable.get('cpu', '0'))
            memory_allocatable = parse_memory(allocatable.get('memory', '0'))

            total_cpu_capacity += cpu_capacity
            total_memory_capacity += memory_capacity
            total_cpu_allocatable += cpu_allocatable
            total_memory_allocatable += memory_allocatable

            # 노드 아키텍처
            arch = labels.get('kubernetes.io/arch', 'unknown')

            nodes_info.append({
                'name': node_name,
                'ready': is_ready,
                'architecture': arch,
                'role': 'master' if 'node-role.kubernetes.io/master' in labels or 'node-role.kubernetes.io/control-plane' in labels else 'worker',
                'cpu_capacity_millicores': cpu_capacity,
                'memory_capacity_bytes': memory_capacity,
                'cpu_allocatable_millicores': cpu_allocatable,
                'memory_allocatable_bytes': memory_allocatable,
                'labels': {k: v for k, v in labels.items() if not k.startswith('beta.kubernetes.io')}
            })

        logger.info(f"Collected metrics for {len(nodes_info)} nodes")

    except Exception as e:
        logger.error(f"Failed to collect cluster metrics: {e}")

    return {
        'node_count': len(nodes_info),
        'nodes': nodes_info,
        'total_cpu_capacity_millicores': total_cpu_capacity,
        'total_memory_capacity_bytes': total_memory_capacity,
        'total_cpu_allocatable_millicores': total_cpu_allocatable,
        'total_memory_allocatable_bytes': total_memory_allocatable
    }


# ============================================================
# 워크로드 메트릭 수집
# ============================================================

def collect_workload_metrics(v1: client.CoreV1Api, apps_v1: client.AppsV1Api) -> Dict[str, Any]:
    """워크로드 메트릭 수집 (Pod, Deployment 상태)"""

    pods_info = []
    deployments_info = []

    try:
        # Pod 정보 수집
        pods = v1.list_pod_for_all_namespaces()

        for pod in pods.items:
            # 시스템 네임스페이스 제외 옵션
            ns = pod.metadata.namespace
            if ns in ['kube-system', 'kube-public', 'kube-node-lease']:
                continue

            phase = pod.status.phase
            node_name = pod.spec.node_name or 'unscheduled'

            # 컨테이너 리소스 요청/제한 합산
            cpu_request = 0
            memory_request = 0
            cpu_limit = 0
            memory_limit = 0

            for container in pod.spec.containers:
                resources = container.resources or client.V1ResourceRequirements()
                requests = resources.requests or {}
                limits = resources.limits or {}

                cpu_request += parse_cpu(requests.get('cpu', '0'))
                memory_request += parse_memory(requests.get('memory', '0'))
                cpu_limit += parse_cpu(limits.get('cpu', '0'))
                memory_limit += parse_memory(limits.get('memory', '0'))

            pods_info.append({
                'name': pod.metadata.name,
                'namespace': ns,
                'phase': phase,
                'node': node_name,
                'cpu_request_millicores': cpu_request,
                'memory_request_bytes': memory_request,
                'cpu_limit_millicores': cpu_limit,
                'memory_limit_bytes': memory_limit,
                'labels': pod.metadata.labels or {}
            })

        # Deployment 정보 수집
        deployments = apps_v1.list_deployment_for_all_namespaces()

        for deploy in deployments.items:
            ns = deploy.metadata.namespace
            if ns in ['kube-system', 'kube-public', 'kube-node-lease']:
                continue

            deployments_info.append({
                'name': deploy.metadata.name,
                'namespace': ns,
                'replicas_desired': deploy.spec.replicas or 0,
                'replicas_ready': deploy.status.ready_replicas or 0,
                'replicas_available': deploy.status.available_replicas or 0,
                'labels': deploy.metadata.labels or {}
            })

        logger.info(f"Collected metrics for {len(pods_info)} pods, {len(deployments_info)} deployments")

    except Exception as e:
        logger.error(f"Failed to collect workload metrics: {e}")

    return {
        'pod_count': len(pods_info),
        'pods': pods_info,
        'deployment_count': len(deployments_info),
        'deployments': deployments_info
    }


# ============================================================
# 범용 디바이스 메트릭 수집 (InfluxDB)
# ============================================================

def collect_device_metrics(influx_client: InfluxDBClient) -> Dict[str, Any]:
    """범용 디바이스 메트릭 수집 - InfluxDB에서 조회 (SDR/SDA/SDV/UNKNOWN)"""

    devices = []

    try:
        query_api = influx_client.query_api()

        # 최근 5분 내의 고유 디바이스 목록 조회
        device_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -5m)
            |> filter(fn: (r) => r._measurement == "power" or r._measurement == "battery")
            |> group(columns: ["bot", "device_type"])
            |> distinct(column: "bot")
        '''

        device_tables = query_api.query(device_query, org=INFLUX_ORG)
        device_map = {}  # bot_name -> device_type

        for table in device_tables:
            for record in table.records:
                bot_name = record.values.get('bot', 'unknown')
                device_type = record.values.get('device_type', 'UNKNOWN')
                device_map[bot_name] = device_type

        # 각 디바이스별 최신 메트릭 조회
        for bot_name, device_type in device_map.items():
            device_data = build_universal_device_schema(
                query_api, bot_name, device_type
            )
            devices.append(device_data)

        logger.info(f"Collected metrics for {len(devices)} devices")

    except Exception as e:
        logger.error(f"Failed to collect device metrics: {e}")

    return {
        'device_count': len(devices),
        'devices': devices
    }


def build_universal_device_schema(query_api, bot_name: str, device_type: str) -> Dict[str, Any]:
    """범용 디바이스 스키마 구성"""

    device_data = {
        'device_id': bot_name,
        'device_type': device_type,
        'device_model': infer_device_model(bot_name),
        'cluster_id': CLUSTER_ID,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': 'online',

        'power': {
            'type': 'battery',
            'percentage': 0.0,
            'voltage': 0.0,
            'current': 0.0,
            'wh_remaining': 0.0,
            'wh_capacity': 0.0,
            'charging': False,
            'temperature': 0.0
        },

        'position': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0,
            'latitude': None,
            'longitude': None,
            'altitude': None,
            'heading': 0.0,
            'coordinate_system': 'local'
        },

        'motion': {
            'linear_velocity': 0.0,
            'angular_velocity': 0.0,
            'acceleration_x': 0.0,
            'acceleration_y': 0.0,
            'acceleration_z': 0.0,
            'speed': 0.0,
            'moving': False
        },

        'environment': {
            'obstacle_min_distance': -1.0,
            'obstacle_front_distance': -1.0,
            'temperature': None,
            'humidity': None,
            'wind_speed': None,
            'wind_direction': None
        },

        'sensors': {
            'lidar': {'active': False, 'points': 0},
            'camera': {'active': False, 'resolution': None},
            'imu': {'active': False},
            'gps': {'active': False, 'satellites': 0},
            'ultrasonic': {'active': False}
        },

        'mission': {
            'task_id': None,
            'task_name': None,
            'task_status': 'idle',
            'progress': 0,
            'waypoints_total': 0,
            'waypoints_completed': 0
        },

        'health': {
            'cpu_usage': None,
            'memory_usage': None,
            'disk_usage': None,
            'network_latency': None,
            'error_count': 0,
            'last_error': None
        },

        'compute': {
            'cpu': {
                'cores': 0,
                'model': None,
                'architecture': None,
                'frequency_mhz': 0,
                'usage_percent': 0.0
            },
            'memory': {
                'total_bytes': 0,
                'available_bytes': 0,
                'used_bytes': 0,
                'usage_percent': 0.0
            },
            'disk': {
                'type': None,
                'total_bytes': 0,
                'available_bytes': 0,
                'used_bytes': 0,
                'usage_percent': 0.0
            },
            'gpu': {
                'available': False,
                'name': None,
                'model': None,
                'memory_total_bytes': 0,
                'memory_used_bytes': 0,
                'memory_usage_percent': 0.0,
                'utilization_percent': 0.0
            },
            'npu': {
                'available': False,
                'name': None,
                'model': None,
                'utilization_percent': 0.0
            }
        },

        'custom': {},
        'last_seen': None
    }

    # 각 measurement에서 최신 데이터 쿼리
    measurements = ['power', 'position', 'motion', 'environment', 'sensors', 'mission', 'health', 'compute']

    for measurement in measurements:
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -5m)
            |> filter(fn: (r) => r._measurement == "{measurement}" and r.bot == "{bot_name}")
            |> last()
        '''

        try:
            tables = query_api.query(query, org=INFLUX_ORG)
            for table in tables:
                for record in table.records:
                    field = record.get_field()
                    value = record.get_value()

                    if measurement == 'power':
                        if field in device_data['power']:
                            device_data['power'][field] = value
                    elif measurement == 'position':
                        if field in device_data['position']:
                            device_data['position'][field] = value
                    elif measurement == 'motion':
                        if field in device_data['motion']:
                            device_data['motion'][field] = value
                        # moving 플래그 계산
                        if field == 'linear_velocity' and abs(value) > 0.01:
                            device_data['motion']['moving'] = True
                    elif measurement == 'environment':
                        if field in device_data['environment']:
                            device_data['environment'][field] = value
                    elif measurement == 'sensors':
                        # 센서 활성 상태 매핑
                        if field == 'lidar_active':
                            device_data['sensors']['lidar']['active'] = value
                        elif field == 'camera_active':
                            device_data['sensors']['camera']['active'] = value
                        elif field == 'imu_active':
                            device_data['sensors']['imu']['active'] = value
                        elif field == 'gps_active':
                            device_data['sensors']['gps']['active'] = value
                        elif field == 'gps_satellites':
                            device_data['sensors']['gps']['satellites'] = value
                    elif measurement == 'mission':
                        if field in device_data['mission']:
                            device_data['mission'][field] = value
                    elif measurement == 'health':
                        if field in device_data['health']:
                            device_data['health'][field] = value
                    elif measurement == 'compute':
                        # compute 필드 매핑
                        if field.startswith('cpu_'):
                            key = field.replace('cpu_', '')
                            if key in device_data['compute']['cpu']:
                                device_data['compute']['cpu'][key] = value
                        elif field.startswith('memory_'):
                            key = field.replace('memory_', '')
                            if key in device_data['compute']['memory']:
                                device_data['compute']['memory'][key] = value
                        elif field.startswith('disk_'):
                            key = field.replace('disk_', '')
                            if key in device_data['compute']['disk']:
                                device_data['compute']['disk'][key] = value
                        elif field.startswith('gpu_'):
                            key = field.replace('gpu_', '')
                            if key in device_data['compute']['gpu']:
                                device_data['compute']['gpu'][key] = value
                        elif field.startswith('npu_'):
                            key = field.replace('npu_', '')
                            if key in device_data['compute']['npu']:
                                device_data['compute']['npu'][key] = value

                    # last_seen 업데이트
                    device_data['last_seen'] = record.get_time().isoformat()

        except Exception as e:
            logger.debug(f"No {measurement} data for {bot_name}: {e}")

    # 기존 battery/pose 측정값도 호환성을 위해 쿼리 (fallback)
    fallback_queries = [
        ('battery', 'power', ['percentage', 'voltage', 'wh']),
        ('pose', 'position', ['x', 'y'])
    ]

    for old_measurement, new_section, fields in fallback_queries:
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -5m)
            |> filter(fn: (r) => r._measurement == "{old_measurement}" and r.bot == "{bot_name}")
            |> last()
        '''
        try:
            tables = query_api.query(query, org=INFLUX_ORG)
            for table in tables:
                for record in table.records:
                    field = record.get_field()
                    value = record.get_value()
                    if field in fields:
                        if new_section == 'power':
                            if field == 'wh':
                                device_data['power']['wh_remaining'] = value
                            else:
                                device_data['power'][field] = value
                        elif new_section == 'position':
                            device_data['position'][field] = value
                    device_data['last_seen'] = record.get_time().isoformat()
        except:
            pass

    return device_data


def infer_device_model(bot_name: str) -> str:
    """봇 이름으로 디바이스 모델 추론"""
    name_lower = bot_name.lower()
    if 'burger' in name_lower:
        return 'turtlebot3_burger'
    elif 'waffle' in name_lower:
        return 'turtlebot3_waffle'
    elif 'turtlebot' in name_lower:
        return 'turtlebot3'
    elif 'drone' in name_lower:
        return 'generic_drone'
    elif 'agv' in name_lower:
        return 'generic_agv'
    else:
        return 'unknown'


# ============================================================
# 유틸리티 함수
# ============================================================

def parse_cpu(cpu_str: str) -> int:
    """CPU 문자열을 millicores로 변환"""
    if not cpu_str:
        return 0
    cpu_str = str(cpu_str)
    if cpu_str.endswith('m'):
        return int(cpu_str[:-1])
    elif cpu_str.endswith('n'):
        return int(cpu_str[:-1]) // 1_000_000
    else:
        return int(float(cpu_str) * 1000)


def parse_memory(mem_str: str) -> int:
    """메모리 문자열을 bytes로 변환"""
    if not mem_str:
        return 0
    mem_str = str(mem_str)

    units = {
        'Ki': 1024,
        'Mi': 1024 ** 2,
        'Gi': 1024 ** 3,
        'Ti': 1024 ** 4,
        'K': 1000,
        'M': 1000 ** 2,
        'G': 1000 ** 3,
        'T': 1000 ** 4,
    }

    for suffix, multiplier in units.items():
        if mem_str.endswith(suffix):
            return int(float(mem_str[:-len(suffix)]) * multiplier)

    return int(mem_str)


# ============================================================
# Central Cluster로 메트릭 전송
# ============================================================

def send_to_central(payload: Dict[str, Any]) -> bool:
    """Central Cluster API로 메트릭 전송"""

    url = f"{CENTRAL_API_URL}/api/v1/federation/metrics"
    headers = {
        'Content-Type': 'application/json',
        'X-Cluster-ID': CLUSTER_ID
    }

    if CENTRAL_API_TOKEN:
        headers['Authorization'] = f'Bearer {CENTRAL_API_TOKEN}'

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 201, 202]:
                logger.info(f"Successfully sent metrics to Central Cluster (attempt {attempt})")
                return True
            else:
                logger.warning(f"Central returned status {response.status_code}: {response.text}")

        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection to Central failed (attempt {attempt}/{MAX_RETRIES})")
        except requests.exceptions.Timeout:
            logger.warning(f"Request to Central timed out (attempt {attempt}/{MAX_RETRIES})")
        except Exception as e:
            logger.error(f"Unexpected error sending to Central: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    logger.error("Failed to send metrics to Central after all retries")
    return False


# ============================================================
# 메인 루프
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("Metric Federation Agent Starting...")
    logger.info(f"  Cluster ID: {CLUSTER_ID}")
    logger.info(f"  Cluster Name: {CLUSTER_NAME}")
    logger.info(f"  Central API: {CENTRAL_API_URL}")
    logger.info(f"  Sync Interval: {SYNC_INTERVAL}s")
    logger.info(f"  Device Types: SDR, SDA, SDV, UNKNOWN")
    logger.info("=" * 60)

    # Kubernetes 클라이언트 초기화
    v1, apps_v1 = init_k8s_client()

    # InfluxDB 클라이언트 초기화
    influx_client = None
    if INFLUX_TOKEN:
        try:
            influx_client = InfluxDBClient(
                url=INFLUX_URL,
                token=INFLUX_TOKEN,
                org=INFLUX_ORG
            )
            logger.info("InfluxDB client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize InfluxDB client: {e}")

    # 메인 동기화 루프
    while True:
        try:
            timestamp = datetime.now(timezone.utc).isoformat()

            # 메트릭 수집
            cluster_metrics = collect_cluster_metrics(v1)
            workload_metrics = collect_workload_metrics(v1, apps_v1)
            device_metrics = collect_device_metrics(influx_client) if influx_client else {'device_count': 0, 'devices': []}

            # 전송 페이로드 구성
            payload = {
                'cluster_id': CLUSTER_ID,
                'cluster_name': CLUSTER_NAME,
                'timestamp': timestamp,
                'cluster_metrics': cluster_metrics,
                'workload_metrics': workload_metrics,
                'device_metrics': device_metrics
            }

            # Central로 전송
            send_to_central(payload)

            logger.info(f"Sync completed. Next sync in {SYNC_INTERVAL}s")

        except Exception as e:
            logger.exception(f"Error in main loop: {e}")

        time.sleep(SYNC_INTERVAL)


if __name__ == '__main__':
    main()
