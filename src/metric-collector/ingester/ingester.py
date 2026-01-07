# ingester.py
# =============================================================================
# Universal Device Telemetry Ingester
# SDR (Robot) / SDA (Air) / SDV (Vehicle) / UNKNOWN 지원
# =============================================================================

import os
import json
import logging
from datetime import datetime, timezone
import pika
from influxdb_client import InfluxDBClient, Point, WriteOptions

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# RabbitMQ 연결 설정
cred = pika.PlainCredentials(
    os.getenv('RABBITMQ_USER', 'rabbit'),
    os.getenv('RABBITMQ_PASS', 'rabbit')
)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST', 'rabbitmq'),
        credentials=cred,
        heartbeat=30,
        connection_attempts=5,
        retry_delay=5,
    )
)
ch = connection.channel()
ch.queue_declare(queue='turtlebot.telemetry', durable=True)

# InfluxDB 연결 설정
client = InfluxDBClient(
    url=os.getenv('INFLUX_URL', 'http://influxdb:8086'),
    token=os.getenv('INFLUX_TOKEN'),
    org=os.getenv('INFLUX_ORG', 'keti')
)
write = client.write_api(write_options=WriteOptions(batch_size=1))
bucket = os.getenv('INFLUX_BUCKET', 'turtlebot')


def infer_device_type(bot_name: str) -> str:
    """봇 이름으로 디바이스 타입 추론"""
    name_lower = bot_name.lower()
    if 'turtlebot' in name_lower or 'robot' in name_lower or 'burger' in name_lower:
        return 'SDR'
    elif 'drone' in name_lower or 'uav' in name_lower or 'air' in name_lower:
        return 'SDA'
    elif 'vehicle' in name_lower or 'car' in name_lower or 'agv' in name_lower:
        return 'SDV'
    else:
        return 'UNKNOWN'


def cb(ch, method, props, body):
    try:
        d = json.loads(body)
        msg_type = d.get("type")

        # telemetry 메시지가 아니면 ACK만 하고 버리기
        if msg_type != "telemetry":
            logger.warning(f"Unknown message type: {msg_type!r}, discarding")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # timestamp 변환
        t = datetime.fromtimestamp(d["ts"] / 1e9, tz=timezone.utc)
        bot = d.get("bot", "unknown")
        device_type = d.get("device_type", infer_device_type(bot))

        # ============================================================
        # 1. 전원/배터리 데이터 (power measurement)
        # ============================================================
        batt = d.get("battery", {})
        power = d.get("power", batt)  # 새 스키마 또는 기존 스키마 호환

        pt_power = (
            Point("power")
            .tag("bot", bot)
            .tag("device_type", device_type)
            .field("percentage", float(power.get("percentage", 0.0)))
            .field("voltage", float(power.get("voltage", 0.0)))
            .field("current", float(power.get("current", 0.0)))
            .field("wh_remaining", float(power.get("wh", power.get("wh_remaining", 0.0))))
            .field("wh_capacity", float(power.get("wh_capacity", 0.0)))
            .field("charging", bool(power.get("charging", False)))
            .field("temperature", float(power.get("temperature", 0.0)))
            .time(t)
        )
        write.write(bucket=bucket, record=pt_power)

        # ============================================================
        # 2. 위치 데이터 (position measurement)
        # ============================================================
        pose = d.get("pose", {})
        position = d.get("position", pose)  # 새 스키마 또는 기존 스키마 호환

        pt_position = (
            Point("position")
            .tag("bot", bot)
            .tag("device_type", device_type)
            .field("x", float(position.get("x", 0.0)))
            .field("y", float(position.get("y", 0.0)))
            .field("z", float(position.get("z", 0.0)))
            .field("latitude", float(position.get("latitude", 0.0)))
            .field("longitude", float(position.get("longitude", 0.0)))
            .field("altitude", float(position.get("altitude", 0.0)))
            .field("heading", float(position.get("heading", 0.0)))
            .time(t)
        )
        write.write(bucket=bucket, record=pt_position)

        # ============================================================
        # 3. 모션 데이터 (motion measurement)
        # ============================================================
        motion = d.get("motion", {})

        pt_motion = (
            Point("motion")
            .tag("bot", bot)
            .tag("device_type", device_type)
            .field("linear_velocity", float(motion.get("linear_velocity", 0.0)))
            .field("angular_velocity", float(motion.get("angular_velocity", 0.0)))
            .field("acceleration_x", float(motion.get("acceleration_x", 0.0)))
            .field("acceleration_y", float(motion.get("acceleration_y", 0.0)))
            .field("acceleration_z", float(motion.get("acceleration_z", 0.0)))
            .field("speed", float(motion.get("speed", 0.0)))
            .time(t)
        )
        write.write(bucket=bucket, record=pt_motion)

        # ============================================================
        # 4. 환경 센서 데이터 (environment measurement)
        # ============================================================
        env = d.get("env", d.get("environment", {}))

        pt_env = (
            Point("environment")
            .tag("bot", bot)
            .tag("device_type", device_type)
            .field("obstacle_min_distance", float(env.get("obstacle_min", env.get("obstacle_min_distance", -1.0))))
            .field("obstacle_front_distance", float(env.get("obstacle_front", env.get("obstacle_front_distance", -1.0))))
            .field("temperature", float(env.get("temperature", 0.0)))
            .field("humidity", float(env.get("humidity", 0.0)))
            .field("wind_speed", float(env.get("wind_speed", 0.0)))
            .field("wind_direction", float(env.get("wind_direction", 0.0)))
            .time(t)
        )
        write.write(bucket=bucket, record=pt_env)

        # ============================================================
        # 5. 센서 상태 데이터 (sensors measurement)
        # ============================================================
        sensors = d.get("sensors", {})
        if sensors:
            pt_sensors = (
                Point("sensors")
                .tag("bot", bot)
                .tag("device_type", device_type)
                .field("lidar_active", bool(sensors.get("lidar", {}).get("active", False)))
                .field("camera_active", bool(sensors.get("camera", {}).get("active", False)))
                .field("imu_active", bool(sensors.get("imu", {}).get("active", False)))
                .field("gps_active", bool(sensors.get("gps", {}).get("active", False)))
                .field("gps_satellites", int(sensors.get("gps", {}).get("satellites", 0)))
                .time(t)
            )
            write.write(bucket=bucket, record=pt_sensors)

        # ============================================================
        # 6. 미션 상태 데이터 (mission measurement)
        # ============================================================
        mission = d.get("mission", {})
        if mission:
            pt_mission = (
                Point("mission")
                .tag("bot", bot)
                .tag("device_type", device_type)
                .tag("task_id", str(mission.get("task_id", "")))
                .field("task_status", str(mission.get("task_status", "idle")))
                .field("progress", float(mission.get("progress", 0.0)))
                .field("waypoints_total", int(mission.get("waypoints_total", 0)))
                .field("waypoints_completed", int(mission.get("waypoints_completed", 0)))
                .time(t)
            )
            write.write(bucket=bucket, record=pt_mission)

        # ============================================================
        # 7. 시스템 헬스 데이터 (health measurement)
        # ============================================================
        health = d.get("health", {})
        if health:
            pt_health = (
                Point("health")
                .tag("bot", bot)
                .tag("device_type", device_type)
                .field("cpu_usage", float(health.get("cpu_usage", 0.0)))
                .field("memory_usage", float(health.get("memory_usage", 0.0)))
                .field("disk_usage", float(health.get("disk_usage", 0.0)))
                .field("network_latency", float(health.get("network_latency", 0.0)))
                .field("error_count", int(health.get("error_count", 0)))
                .time(t)
            )
            write.write(bucket=bucket, record=pt_health)

        # ============================================================
        # 8. 컴퓨팅 리소스 데이터 (compute measurement)
        # ============================================================
        compute = d.get("compute", {})
        if compute:
            cpu = compute.get("cpu", {})
            memory = compute.get("memory", {})
            disk = compute.get("disk", {})
            gpu = compute.get("gpu", {})
            npu = compute.get("npu", {})

            pt_compute = (
                Point("compute")
                .tag("bot", bot)
                .tag("device_type", device_type)
                # CPU
                .field("cpu_cores", int(cpu.get("cores", 0)))
                .field("cpu_model", str(cpu.get("model", "") or ""))
                .field("cpu_architecture", str(cpu.get("architecture", "") or ""))
                .field("cpu_frequency_mhz", float(cpu.get("frequency_mhz", 0)))
                .field("cpu_usage_percent", float(cpu.get("usage_percent", 0)))
                # Memory
                .field("memory_total_bytes", int(memory.get("total_bytes", 0)))
                .field("memory_available_bytes", int(memory.get("available_bytes", 0)))
                .field("memory_used_bytes", int(memory.get("used_bytes", 0)))
                .field("memory_usage_percent", float(memory.get("usage_percent", 0)))
                # Disk
                .field("disk_type", str(disk.get("type", "") or ""))
                .field("disk_total_bytes", int(disk.get("total_bytes", 0)))
                .field("disk_available_bytes", int(disk.get("available_bytes", 0)))
                .field("disk_used_bytes", int(disk.get("used_bytes", 0)))
                .field("disk_usage_percent", float(disk.get("usage_percent", 0)))
                # GPU
                .field("gpu_available", bool(gpu.get("available", False)))
                .field("gpu_name", str(gpu.get("name", "") or ""))
                .field("gpu_model", str(gpu.get("model", "") or ""))
                .field("gpu_memory_total_bytes", int(gpu.get("memory_total_bytes", 0)))
                .field("gpu_memory_used_bytes", int(gpu.get("memory_used_bytes", 0)))
                .field("gpu_memory_usage_percent", float(gpu.get("memory_usage_percent", 0)))
                .field("gpu_utilization_percent", float(gpu.get("utilization_percent", 0)))
                # NPU
                .field("npu_available", bool(npu.get("available", False)))
                .field("npu_name", str(npu.get("name", "") or ""))
                .field("npu_model", str(npu.get("model", "") or ""))
                .field("npu_utilization_percent", float(npu.get("utilization_percent", 0)))
                .time(t)
            )
            write.write(bucket=bucket, record=pt_compute)

        # ============================================================
        # 9. 커스텀 데이터 (custom measurement) - 타입별 특화 데이터
        # ============================================================
        custom = d.get("custom", {})
        if custom:
            pt_custom = Point("custom").tag("bot", bot).tag("device_type", device_type).time(t)
            for key, value in custom.items():
                if isinstance(value, (int, float)):
                    pt_custom = pt_custom.field(key, float(value))
                elif isinstance(value, bool):
                    pt_custom = pt_custom.field(key, value)
                elif isinstance(value, str):
                    pt_custom = pt_custom.field(key, value)
            write.write(bucket=bucket, record=pt_custom)

        # 정상 처리된 메시지 ACK
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.debug(f"Ingested telemetry from {bot} ({device_type})")

    except Exception:
        logger.exception("ingest error")
        # 처리 불가 에러는 재큐하지 않고 폐기
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Universal Device Telemetry Ingester Starting...")
    logger.info(f"  Supported Types: SDR, SDA, SDV, UNKNOWN")
    logger.info(f"  InfluxDB Bucket: {bucket}")
    logger.info("=" * 60)

    # prefetch 설정: 한 번에 20개 미만만 처리하도록
    ch.basic_qos(prefetch_count=20)
    ch.basic_consume(queue='turtlebot.telemetry', on_message_callback=cb)

    logger.info("Waiting for telemetry messages...")
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down")
    finally:
        if connection and not connection.is_closed:
            connection.close()
