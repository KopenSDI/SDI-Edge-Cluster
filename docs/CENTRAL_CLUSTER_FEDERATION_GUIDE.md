# Central Cluster - Federation Receiver 개발 가이드

## 개요

이 문서는 **Central Cluster (10.0.5.55, Karmada)** 에서 구현해야 할 **Federation Receiver** 컴포넌트에 대한 개발 가이드입니다.

**Edge Cluster**에서는 `metric-federation-agent`가 30초마다 다음 메트릭을 Central로 전송합니다:

- **클러스터 메트릭**: 노드 상태, CPU/메모리 용량
- **워크로드 메트릭**: Pod, Deployment 상태
- **디바이스 메트릭**: 범용 스키마 (SDR/SDA/SDV/UNKNOWN)

### 지원 디바이스 타입

| 타입 | 설명 | 예시 |
|------|------|------|
| **SDR** | Robot (로봇) | TurtleBot, AMR, 협동로봇 |
| **SDA** | Air (항공) | 드론, UAV, 멀티콥터 |
| **SDV** | Vehicle (차량) | AGV, 자율주행차, 배송로봇 |
| **UNKNOWN** | 미분류 | 신규 디바이스 |

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Central Cluster (10.0.5.55)                       │
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Federation       │───▶│ InfluxDB         │◀───│ Dashboard/    │  │
│  │ Receiver API     │    │ (시계열 저장)     │    │ 분석 시스템    │  │
│  │ :30080           │    │ :8086            │    │               │  │
│  └──────────────────┘    └──────────────────┘    └───────────────┘  │
│           ▲                                                          │
└───────────│──────────────────────────────────────────────────────────┘
            │ HTTP POST /api/v1/federation/metrics
            │ (30초마다)
┌───────────│──────────────────────────────────────────────────────────┐
│           │              Edge Cluster (Edge Server)                   │
│  ┌────────┴─────────┐                                                │
│  │ Federation Agent │◀── Kubernetes API + InfluxDB                   │
│  │                  │    (클러스터/워크로드/디바이스 메트릭 수집)       │
│  └──────────────────┘                                                │
│       ▲                                                              │
│       │ RabbitMQ                                                     │
│  ┌────┴─────────────┐                                                │
│  │ SDR/SDA/SDV      │  TurtleBot, Drone, Vehicle 등                  │
│  │ Devices          │                                                │
│  └──────────────────┘                                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 1. Federation Receiver API 스펙

### 엔드포인트

```
POST /api/v1/federation/metrics
```

### 요청 헤더

| 헤더 | 설명 | 예시 |
|------|------|------|
| `Content-Type` | 항상 JSON | `application/json` |
| `X-Cluster-ID` | Edge Cluster 식별자 | `edge-cluster-01` |
| `Authorization` | Bearer 토큰 (선택) | `Bearer <token>` |

---

## 2. 범용 디바이스 스키마 (Universal Device Schema)

### 전체 페이로드 구조

```json
{
  "cluster_id": "edge-cluster-01",
  "cluster_name": "KETI-Edge-Cluster",
  "timestamp": "2026-01-07T10:30:00.000Z",

  "cluster_metrics": { ... },
  "workload_metrics": { ... },
  "device_metrics": {
    "device_count": 2,
    "devices": [
      { /* 범용 디바이스 스키마 */ }
    ]
  }
}
```

### 범용 디바이스 스키마 상세

```json
{
  "device_id": "turtlebot-burger-3",
  "device_type": "SDR",
  "device_model": "turtlebot3_burger",
  "cluster_id": "edge-cluster-01",
  "timestamp": "2026-01-07T10:30:00.000Z",
  "status": "online",

  "power": {
    "type": "battery",
    "percentage": 82.5,
    "voltage": 12.0,
    "current": 1.5,
    "wh_remaining": 16.4,
    "wh_capacity": 20.0,
    "charging": false,
    "temperature": 25.0
  },

  "position": {
    "x": 1.5,
    "y": 2.3,
    "z": 0.0,
    "latitude": null,
    "longitude": null,
    "altitude": null,
    "heading": 45.0,
    "coordinate_system": "local"
  },

  "motion": {
    "linear_velocity": 0.15,
    "angular_velocity": 0.02,
    "acceleration_x": 0.01,
    "acceleration_y": 0.0,
    "acceleration_z": 0.0,
    "speed": 0.15,
    "moving": true
  },

  "environment": {
    "obstacle_min_distance": 0.35,
    "obstacle_front_distance": 1.2,
    "temperature": null,
    "humidity": null,
    "wind_speed": null,
    "wind_direction": null
  },

  "sensors": {
    "lidar": {"active": true, "points": 360},
    "camera": {"active": false, "resolution": null},
    "imu": {"active": true},
    "gps": {"active": false, "satellites": 0},
    "ultrasonic": {"active": false}
  },

  "mission": {
    "task_id": null,
    "task_name": null,
    "task_status": "idle",
    "progress": 0,
    "waypoints_total": 0,
    "waypoints_completed": 0
  },

  "health": {
    "cpu_usage": null,
    "memory_usage": null,
    "disk_usage": null,
    "network_latency": null,
    "error_count": 0,
    "last_error": null
  },

  "compute": {
    "cpu": {
      "cores": 4,
      "model": "ARM Cortex-A72",
      "architecture": "aarch64",
      "frequency_mhz": 1500,
      "usage_percent": 25.5
    },
    "memory": {
      "total_bytes": 4294967296,
      "available_bytes": 2147483648,
      "used_bytes": 2147483648,
      "usage_percent": 50.0
    },
    "disk": {
      "type": "eMMC",
      "total_bytes": 64424509440,
      "available_bytes": 32212254720,
      "used_bytes": 32212254720,
      "usage_percent": 50.0
    },
    "gpu": {
      "available": true,
      "name": "NVIDIA Jetson",
      "model": "Jetson Nano",
      "memory_total_bytes": 4294967296,
      "memory_used_bytes": 1073741824,
      "memory_usage_percent": 25.0,
      "utilization_percent": 30.0
    },
    "npu": {
      "available": false,
      "name": null,
      "model": null,
      "utilization_percent": 0
    }
  },

  "custom": {},
  "last_seen": "2026-01-07T10:29:55.000Z"
}
```

### 필드 설명

#### 기본 정보
| 필드 | 타입 | 설명 |
|------|------|------|
| `device_id` | string | 디바이스 고유 식별자 |
| `device_type` | string | SDR / SDA / SDV / UNKNOWN |
| `device_model` | string | 구체적 모델명 (turtlebot3_burger 등) |
| `status` | string | online / offline / error / maintenance |

#### power (전원)
| 필드 | 타입 | 설명 |
|------|------|------|
| `type` | string | battery / fuel / hybrid / electric |
| `percentage` | float | 잔량 비율 (0.0 ~ 1.0) |
| `voltage` | float | 전압 (V) |
| `current` | float | 전류 (A) |
| `wh_remaining` | float | 남은 용량 (Wh) |
| `wh_capacity` | float | 전체 용량 (Wh) |
| `charging` | bool | 충전 중 여부 |
| `temperature` | float | 배터리 온도 (°C) |

#### position (위치)
| 필드 | 타입 | 설명 |
|------|------|------|
| `x`, `y`, `z` | float | 로컬 좌표 (m) |
| `latitude`, `longitude` | float | GPS 좌표 |
| `altitude` | float | GPS 고도 (m) |
| `heading` | float | 방향각 (도) |
| `coordinate_system` | string | local / gps / utm |

#### motion (움직임)
| 필드 | 타입 | 설명 |
|------|------|------|
| `linear_velocity` | float | 선속도 (m/s) |
| `angular_velocity` | float | 각속도 (rad/s) |
| `acceleration_x/y/z` | float | 가속도 (m/s²) |
| `speed` | float | 종합 속도 (m/s) |
| `moving` | bool | 이동 중 여부 |

#### environment (환경)
| 필드 | 타입 | 설명 |
|------|------|------|
| `obstacle_min_distance` | float | 최근접 장애물 거리 (m) |
| `obstacle_front_distance` | float | 전방 장애물 거리 (m) |
| `temperature` | float | 외부 온도 (°C) |
| `humidity` | float | 습도 (%) |
| `wind_speed` | float | 풍속 (m/s) - 드론용 |
| `wind_direction` | float | 풍향 (도) - 드론용 |

#### sensors (센서 상태)
| 필드 | 타입 | 설명 |
|------|------|------|
| `lidar.active` | bool | 라이다 활성 |
| `camera.active` | bool | 카메라 활성 |
| `imu.active` | bool | IMU 활성 |
| `gps.active` | bool | GPS 활성 |
| `gps.satellites` | int | GPS 위성 수 |

#### mission (미션)
| 필드 | 타입 | 설명 |
|------|------|------|
| `task_id` | string | 현재 태스크 ID |
| `task_status` | string | idle / running / paused / completed / failed |
| `progress` | float | 진행률 (0~100) |
| `waypoints_total` | int | 총 웨이포인트 수 |
| `waypoints_completed` | int | 완료 웨이포인트 수 |

#### health (시스템 상태)
| 필드 | 타입 | 설명 |
|------|------|------|
| `cpu_usage` | float | CPU 사용률 (%) |
| `memory_usage` | float | 메모리 사용률 (%) |
| `disk_usage` | float | 디스크 사용률 (%) |
| `error_count` | int | 에러 발생 횟수 |

#### compute (컴퓨팅 리소스) - 공통
| 필드 | 타입 | 설명 |
|------|------|------|
| `cpu.cores` | int | CPU 코어 수 |
| `cpu.model` | string | CPU 모델명 (ARM Cortex-A72 등) |
| `cpu.architecture` | string | CPU 아키텍처 (aarch64, x86_64 등) |
| `cpu.frequency_mhz` | float | CPU 클럭 속도 (MHz) |
| `cpu.usage_percent` | float | CPU 사용률 (%) |
| `memory.total_bytes` | int | 전체 RAM 용량 |
| `memory.available_bytes` | int | 사용 가능 RAM |
| `memory.used_bytes` | int | 사용 중 RAM |
| `memory.usage_percent` | float | 메모리 사용률 (%) |
| `disk.type` | string | 디스크 타입 (SSD, HDD, NVMe, eMMC 등) |
| `disk.total_bytes` | int | 전체 디스크 용량 |
| `disk.available_bytes` | int | 사용 가능 디스크 |
| `disk.used_bytes` | int | 사용 중 디스크 |
| `disk.usage_percent` | float | 디스크 사용률 (%) |
| `gpu.available` | bool | GPU 장착 여부 |
| `gpu.name` | string | GPU 이름 (NVIDIA Jetson 등) |
| `gpu.model` | string | GPU 모델명 (Jetson Nano, RTX 4090 등) |
| `gpu.memory_total_bytes` | int | GPU 전체 메모리 |
| `gpu.memory_used_bytes` | int | GPU 사용 중 메모리 |
| `gpu.memory_usage_percent` | float | GPU 메모리 사용률 (%) |
| `gpu.utilization_percent` | float | GPU 연산 사용률 (%) |
| `npu.available` | bool | NPU 장착 여부 |
| `npu.name` | string | NPU 이름 (Edge TPU, Hailo-8 등) |
| `npu.model` | string | NPU 모델명 |
| `npu.utilization_percent` | float | NPU 사용률 (%) |

#### custom (타입별 특화 데이터)
device_type별로 다른 데이터를 담을 수 있는 확장 필드입니다.

```json
// SDR (Robot)
"custom": {
  "arm_position": [0, 45, 90],
  "gripper_state": "open"
}

// SDA (Air)
"custom": {
  "flight_mode": "hover",
  "propeller_rpm": [1000, 1000, 1000, 1000]
}

// SDV (Vehicle)
"custom": {
  "cargo_weight": 500,
  "door_status": "closed"
}
```

---

## 3. 클러스터 메트릭

```json
"cluster_metrics": {
  "node_count": 3,
  "nodes": [
    {
      "name": "keti-csm",
      "ready": true,
      "architecture": "amd64",
      "role": "master",
      "cpu_capacity_millicores": 8000,
      "memory_capacity_bytes": 16106127360,
      "cpu_allocatable_millicores": 7900,
      "memory_allocatable_bytes": 15900000000,
      "labels": {}
    }
  ],
  "total_cpu_capacity_millicores": 16000,
  "total_memory_capacity_bytes": 24000000000,
  "total_cpu_allocatable_millicores": 15800,
  "total_memory_allocatable_bytes": 23000000000
}
```

---

## 4. 워크로드 메트릭

```json
"workload_metrics": {
  "pod_count": 18,
  "pods": [
    {
      "name": "metric-federation-agent-xxx",
      "namespace": "keti-monitoring",
      "phase": "Running",
      "node": "keti-csm",
      "cpu_request_millicores": 50,
      "memory_request_bytes": 67108864,
      "labels": {}
    }
  ],
  "deployment_count": 12,
  "deployments": [
    {
      "name": "metric-federation-agent",
      "namespace": "keti-monitoring",
      "replicas_desired": 1,
      "replicas_ready": 1,
      "replicas_available": 1,
      "labels": {}
    }
  ]
}
```

---

## 5. Federation Receiver 구현 예제

### Python FastAPI 구현

```python
"""
Federation Receiver for Central Cluster
========================================
Edge Cluster로부터 범용 디바이스 메트릭을 수신하여 저장
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 환경 변수
INFLUX_URL = os.getenv('INFLUX_URL', 'http://localhost:8086')
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN', '')
INFLUX_ORG = os.getenv('INFLUX_ORG', 'keti')
INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', 'federation')
API_TOKEN = os.getenv('API_TOKEN', 'temp-token-for-testing')

# InfluxDB 클라이언트
influx_client = None
write_api = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global influx_client, write_api
    influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)
    logger.info(f"Connected to InfluxDB: {INFLUX_URL}")
    yield
    if influx_client:
        influx_client.close()

app = FastAPI(title="Federation Receiver", lifespan=lifespan)


# ============================================================
# Pydantic 모델
# ============================================================

class PowerMetrics(BaseModel):
    type: str = "battery"
    percentage: float = 0.0
    voltage: float = 0.0
    current: float = 0.0
    wh_remaining: float = 0.0
    wh_capacity: float = 0.0
    charging: bool = False
    temperature: float = 0.0

class PositionMetrics(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    heading: float = 0.0
    coordinate_system: str = "local"

class MotionMetrics(BaseModel):
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    acceleration_x: float = 0.0
    acceleration_y: float = 0.0
    acceleration_z: float = 0.0
    speed: float = 0.0
    moving: bool = False

class EnvironmentMetrics(BaseModel):
    obstacle_min_distance: float = -1.0
    obstacle_front_distance: float = -1.0
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None

class MissionMetrics(BaseModel):
    task_id: Optional[str] = None
    task_name: Optional[str] = None
    task_status: str = "idle"
    progress: float = 0.0
    waypoints_total: int = 0
    waypoints_completed: int = 0

class HealthMetrics(BaseModel):
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    network_latency: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None

class CpuInfo(BaseModel):
    cores: int = 0
    model: Optional[str] = None
    architecture: Optional[str] = None
    frequency_mhz: float = 0
    usage_percent: float = 0.0

class MemoryInfo(BaseModel):
    total_bytes: int = 0
    available_bytes: int = 0
    used_bytes: int = 0
    usage_percent: float = 0.0

class DiskInfo(BaseModel):
    type: Optional[str] = None  # SSD, HDD, NVMe, eMMC
    total_bytes: int = 0
    available_bytes: int = 0
    used_bytes: int = 0
    usage_percent: float = 0.0

class GpuInfo(BaseModel):
    available: bool = False
    name: Optional[str] = None
    model: Optional[str] = None
    memory_total_bytes: int = 0
    memory_used_bytes: int = 0
    memory_usage_percent: float = 0.0
    utilization_percent: float = 0.0

class NpuInfo(BaseModel):
    available: bool = False
    name: Optional[str] = None
    model: Optional[str] = None
    utilization_percent: float = 0.0

class ComputeMetrics(BaseModel):
    cpu: CpuInfo = CpuInfo()
    memory: MemoryInfo = MemoryInfo()
    disk: DiskInfo = DiskInfo()
    gpu: GpuInfo = GpuInfo()
    npu: NpuInfo = NpuInfo()

class UniversalDevice(BaseModel):
    device_id: str
    device_type: str  # SDR, SDA, SDV, UNKNOWN
    device_model: str = "unknown"
    cluster_id: str = ""
    timestamp: str = ""
    status: str = "online"
    power: PowerMetrics = PowerMetrics()
    position: PositionMetrics = PositionMetrics()
    motion: MotionMetrics = MotionMetrics()
    environment: EnvironmentMetrics = EnvironmentMetrics()
    sensors: Dict[str, Any] = {}
    mission: MissionMetrics = MissionMetrics()
    health: HealthMetrics = HealthMetrics()
    compute: ComputeMetrics = ComputeMetrics()
    custom: Dict[str, Any] = {}
    last_seen: Optional[str] = None

class DeviceMetrics(BaseModel):
    device_count: int
    devices: List[UniversalDevice]

class FederationPayload(BaseModel):
    cluster_id: str
    cluster_name: str
    timestamp: str
    cluster_metrics: Dict[str, Any]
    workload_metrics: Dict[str, Any]
    device_metrics: DeviceMetrics


# ============================================================
# API 엔드포인트
# ============================================================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/v1/federation/metrics")
async def receive_metrics(
    payload: FederationPayload,
    x_cluster_id: str = Header(None, alias="X-Cluster-ID"),
    authorization: str = Header(None)
):
    """Edge Cluster로부터 메트릭 수신"""

    # 토큰 검증 (선택)
    if API_TOKEN and authorization:
        token = authorization.replace("Bearer ", "")
        if token != API_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid token")

    cluster_id = x_cluster_id or payload.cluster_id
    timestamp = datetime.fromisoformat(payload.timestamp.replace('Z', '+00:00'))

    try:
        # 1. 클러스터 메트릭 저장
        store_cluster_metrics(cluster_id, payload.cluster_metrics, timestamp)

        # 2. 워크로드 메트릭 저장
        store_workload_metrics(cluster_id, payload.workload_metrics, timestamp)

        # 3. 디바이스 메트릭 저장 (범용 스키마)
        store_device_metrics(cluster_id, payload.device_metrics, timestamp)

        logger.info(
            f"Received from {cluster_id}: "
            f"{payload.cluster_metrics.get('node_count', 0)} nodes, "
            f"{payload.workload_metrics.get('pod_count', 0)} pods, "
            f"{payload.device_metrics.device_count} devices"
        )

        return {
            "status": "accepted",
            "cluster_id": cluster_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.exception(f"Error processing metrics from {cluster_id}")
        raise HTTPException(status_code=500, detail=str(e))


def store_cluster_metrics(cluster_id: str, metrics: Dict, timestamp: datetime):
    """클러스터 메트릭 InfluxDB 저장"""

    # 클러스터 요약
    point = (
        Point("cluster_summary")
        .tag("cluster_id", cluster_id)
        .field("node_count", metrics.get("node_count", 0))
        .field("total_cpu_capacity", metrics.get("total_cpu_capacity_millicores", 0))
        .field("total_memory_capacity", metrics.get("total_memory_capacity_bytes", 0))
        .field("total_cpu_allocatable", metrics.get("total_cpu_allocatable_millicores", 0))
        .field("total_memory_allocatable", metrics.get("total_memory_allocatable_bytes", 0))
        .time(timestamp)
    )
    write_api.write(bucket=INFLUX_BUCKET, record=point)

    # 각 노드별
    for node in metrics.get("nodes", []):
        point = (
            Point("node_status")
            .tag("cluster_id", cluster_id)
            .tag("node_name", node["name"])
            .tag("role", node.get("role", "worker"))
            .tag("architecture", node.get("architecture", "unknown"))
            .field("ready", node.get("ready", False))
            .field("cpu_capacity", node.get("cpu_capacity_millicores", 0))
            .field("memory_capacity", node.get("memory_capacity_bytes", 0))
            .time(timestamp)
        )
        write_api.write(bucket=INFLUX_BUCKET, record=point)


def store_workload_metrics(cluster_id: str, metrics: Dict, timestamp: datetime):
    """워크로드 메트릭 InfluxDB 저장"""

    # 워크로드 요약
    point = (
        Point("workload_summary")
        .tag("cluster_id", cluster_id)
        .field("pod_count", metrics.get("pod_count", 0))
        .field("deployment_count", metrics.get("deployment_count", 0))
        .time(timestamp)
    )
    write_api.write(bucket=INFLUX_BUCKET, record=point)


def store_device_metrics(cluster_id: str, metrics: DeviceMetrics, timestamp: datetime):
    """범용 디바이스 메트릭 InfluxDB 저장"""

    for device in metrics.devices:
        # 1. 디바이스 기본 정보
        point = (
            Point("device_status")
            .tag("cluster_id", cluster_id)
            .tag("device_id", device.device_id)
            .tag("device_type", device.device_type)
            .tag("device_model", device.device_model)
            .field("status", device.status)
            .time(timestamp)
        )
        write_api.write(bucket=INFLUX_BUCKET, record=point)

        # 2. 전원 메트릭
        point = (
            Point("device_power")
            .tag("cluster_id", cluster_id)
            .tag("device_id", device.device_id)
            .tag("device_type", device.device_type)
            .field("percentage", device.power.percentage)
            .field("voltage", device.power.voltage)
            .field("current", device.power.current)
            .field("wh_remaining", device.power.wh_remaining)
            .field("charging", device.power.charging)
            .time(timestamp)
        )
        write_api.write(bucket=INFLUX_BUCKET, record=point)

        # 3. 위치 메트릭
        point = (
            Point("device_position")
            .tag("cluster_id", cluster_id)
            .tag("device_id", device.device_id)
            .tag("device_type", device.device_type)
            .field("x", device.position.x)
            .field("y", device.position.y)
            .field("z", device.position.z)
            .field("heading", device.position.heading)
            .time(timestamp)
        )
        if device.position.latitude:
            point = point.field("latitude", device.position.latitude)
            point = point.field("longitude", device.position.longitude)
        write_api.write(bucket=INFLUX_BUCKET, record=point)

        # 4. 모션 메트릭
        point = (
            Point("device_motion")
            .tag("cluster_id", cluster_id)
            .tag("device_id", device.device_id)
            .tag("device_type", device.device_type)
            .field("linear_velocity", device.motion.linear_velocity)
            .field("angular_velocity", device.motion.angular_velocity)
            .field("speed", device.motion.speed)
            .field("moving", device.motion.moving)
            .time(timestamp)
        )
        write_api.write(bucket=INFLUX_BUCKET, record=point)

        # 5. 환경 메트릭
        point = (
            Point("device_environment")
            .tag("cluster_id", cluster_id)
            .tag("device_id", device.device_id)
            .tag("device_type", device.device_type)
            .field("obstacle_min", device.environment.obstacle_min_distance)
            .field("obstacle_front", device.environment.obstacle_front_distance)
            .time(timestamp)
        )
        write_api.write(bucket=INFLUX_BUCKET, record=point)

        # 6. 미션 메트릭
        if device.mission.task_id:
            point = (
                Point("device_mission")
                .tag("cluster_id", cluster_id)
                .tag("device_id", device.device_id)
                .tag("device_type", device.device_type)
                .tag("task_id", device.mission.task_id)
                .field("task_status", device.mission.task_status)
                .field("progress", device.mission.progress)
                .time(timestamp)
            )
            write_api.write(bucket=INFLUX_BUCKET, record=point)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

## 6. Kubernetes 배포 매니페스트

### federation-receiver-deploy.yaml

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: federation

---
apiVersion: v1
kind: Secret
metadata:
  name: federation-receiver-creds
  namespace: federation
type: Opaque
stringData:
  api-token: "temp-token-for-testing"
  influx-token: "<INFLUX_TOKEN>"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: federation-receiver
  namespace: federation
spec:
  replicas: 1
  selector:
    matchLabels:
      app: federation-receiver
  template:
    metadata:
      labels:
        app: federation-receiver
    spec:
      containers:
        - name: receiver
          image: ketidevit2/federation-receiver:1.0
          ports:
            - containerPort: 8080
          env:
            - name: INFLUX_URL
              value: "http://influxdb.federation.svc:8086"
            - name: INFLUX_TOKEN
              valueFrom:
                secretKeyRef:
                  name: federation-receiver-creds
                  key: influx-token
            - name: INFLUX_ORG
              value: "keti"
            - name: INFLUX_BUCKET
              value: "federation"
            - name: API_TOKEN
              valueFrom:
                secretKeyRef:
                  name: federation-receiver-creds
                  key: api-token
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"

---
apiVersion: v1
kind: Service
metadata:
  name: federation-receiver
  namespace: federation
spec:
  type: NodePort
  selector:
    app: federation-receiver
  ports:
    - port: 8080
      targetPort: 8080
      nodePort: 30080
```

---

## 7. 배포 순서

### Central Cluster에서 실행:

```bash
# 1. InfluxDB 배포 (federation 버킷 생성)
kubectl create ns federation
# InfluxDB 배포 후 federation 버킷 생성

# 2. Federation Receiver 배포
kubectl apply -f federation-receiver-deploy.yaml

# 3. 상태 확인
kubectl get pods -n federation
kubectl logs -n federation -l app=federation-receiver -f

# 4. Health check
curl http://10.0.5.55:30080/health
```

### Edge Cluster에서 실행:

```bash
# 1. Ingester 재배포 (범용 스키마 지원)
kubectl rollout restart deploy/metrics-ingester -n tbot-monitoring

# 2. Federation Agent 재배포
kubectl rollout restart deploy/metric-federation-agent -n keti-monitoring

# 3. 로그 확인
kubectl logs -n keti-monitoring -l app=federation-agent -f
```

---

## 8. 디바이스 타입별 활용

### SDR (Robot) 대시보드 쿼리 예시

```flux
from(bucket: "federation")
  |> range(start: -1h)
  |> filter(fn: (r) => r.device_type == "SDR")
  |> filter(fn: (r) => r._measurement == "device_power")
```

### SDA (Air) 대시보드 쿼리 예시

```flux
from(bucket: "federation")
  |> range(start: -1h)
  |> filter(fn: (r) => r.device_type == "SDA")
  |> filter(fn: (r) => r._measurement == "device_position")
  |> filter(fn: (r) => r._field == "altitude")
```

### 모든 디바이스 현황

```flux
from(bucket: "federation")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "device_status")
  |> group(columns: ["device_type"])
  |> count()
```

---

## 9. 요약

| 항목 | Edge Cluster | Central Cluster |
|------|-------------|-----------------|
| **컴포넌트** | metric-federation-agent | federation-receiver |
| **역할** | 메트릭 수집 및 전송 | 메트릭 수신 및 저장 |
| **통신** | HTTP POST 전송 | FastAPI 서버 |
| **저장소** | 로컬 InfluxDB | 연합 InfluxDB |
| **주기** | 30초마다 전송 | 수신 즉시 저장 |
| **디바이스 스키마** | 범용 (SDR/SDA/SDV/UNKNOWN) | 동일 |

Edge Cluster 측 개발은 완료되어 있습니다. Central Cluster에서는 위의 `federation_receiver.py`를 구현하고 배포하면 연합 모니터링이 동작합니다.
