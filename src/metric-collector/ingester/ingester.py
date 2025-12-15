# ingester.py
import os
import json
import logging
import pika
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point, WriteOptions

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

def cb(ch, method, props, body):
    try:
        d = json.loads(body)
        msg_type = d.get("type")
        # telemetry 메시지가 아니면 ACK만 하고 버리기
        if msg_type != "telemetry":
            logging.warning(f"Unknown message type: {msg_type!r}, discarding")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # timestamp 변환
        t = datetime.fromtimestamp(d["ts"] / 1e9, tz=timezone.utc)
        bot = d.get("bot", "unknown")

        # 배터리 데이터
        batt = d.get("battery", {})
        pt_batt = (
            Point("battery")
            .tag("bot", bot)
            .field("percentage", batt.get("percentage", 0.0))
            .field("voltage", batt.get("voltage", 0.0))
            .field("wh", batt.get("wh", 0.0))
            .time(t)
        )
        write.write(bucket=bucket, record=pt_batt)

        # 포즈 데이터
        pose = d.get("pose", {})
        pt_pose = (
            Point("pose")
            .tag("bot", bot)
            .field("x", pose.get("x", 0.0))
            .field("y", pose.get("y", 0.0))
            .time(t)
        )
        write.write(bucket=bucket, record=pt_pose)

        # 정상 처리된 메시지 ACK
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception:
        logging.exception("ingest error")
        # 처리 불가 에러는 재큐하지 않고 폐기
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

if __name__ == "__main__":
    # prefetch 설정: 한 번에 20개 미만만 처리하도록
    ch.basic_qos(prefetch_count=20)
    ch.basic_consume(queue='turtlebot.telemetry', on_message_callback=cb)
    logging.info("Starting Ingester...")
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        logging.info("Interrupted by user, shutting down")
    finally:
        if connection and not connection.is_closed:
            connection.close()
