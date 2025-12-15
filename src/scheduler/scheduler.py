#!/usr/bin/env python3
import os, time, json, logging, textwrap
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from kubernetes import client, config, watch
from influxdb_client import InfluxDBClient

SCHEDULER_NAME = "sdi-scheduler"

INFLUX_URL    = os.getenv("INFLUX_URL", "http://influxdb.tbot-monitoring.svc.cluster.local:8086")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN")
INFLUX_ORG    = os.getenv("INFLUX_ORG", "keti")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "turtlebot")

QL_BATTERY = textwrap.dedent("""
    from(bucket: "{bucket}")
      |> range(start: -30m)
      |> filter(fn: (r) => r._measurement == "battery" and
                           r.bot == "{bot}" and r._field == "wh")
      |> last()
""")

QL_POSE = textwrap.dedent("""
    from(bucket: "{bucket}")
      |> range(start: -30m)
      |> filter(fn: (r) => r._measurement == "pose" and r.bot == "{bot}" and
                           (r._field == "x" or r._field == "y"))
      |> last()
""")

client_influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=5000)
query_api = client_influx.query_api()

config.load_incluster_config()
v1 = client.CoreV1Api()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
log = logging.getLogger("scheduler")

def latest_wh(bot: str) -> Optional[float]:
    try:
        tables = query_api.query(
            org=INFLUX_ORG,
            query=QL_BATTERY.format(bucket=INFLUX_BUCKET, bot=bot)
        )
        for t in tables:
            for rec in t.records:
                return float(rec.get_value())
    except Exception as e:
        log.warning(f"[query] {bot} 배터리 조회 실패 → {e}")
    return None


def latest_pose(bot: str) -> Optional[Tuple[float, float]]:
    try:
        tables = query_api.query(
            org=INFLUX_ORG,
            query=QL_POSE.format(bucket=INFLUX_BUCKET, bot=bot)
        )
        x = y = None
        for t in tables:
            for rec in t.records:
                if rec.get_field() == "x":
                    x = rec.get_value()
                elif rec.get_field() == "y":
                    y = rec.get_value()
        return (float(x), float(y)) if x is not None and y is not None else None
    except Exception as e:
        log.warning(f"[query] {bot} 위치 조회 실패 → {e}")
    return None


# ───────────── 스케줄링 로직 ─────────────
def make_node_map(nodes):
    m: Dict[str, Dict] = {}
    for n in nodes:
        name = n.metadata.name
        m[name] = {
            "wh":   latest_wh(name),
            "pose": latest_pose(name),
        }
    return m


def first_ready_node(nodes):
    return nodes[0].metadata.name if nodes else None


def choose_node(node_map, nodes):
    avail = {n: v for n, v in node_map.items() if v["wh"] is not None}
    if not avail:
        return first_ready_node(nodes)

    best = max(avail.items(), key=lambda kv: kv[1]["wh"])
    return best[0]


def bind_pod(pod, node_name):
    target = client.V1ObjectReference(kind="Node", api_version="v1", name=node_name)
    meta   = client.V1ObjectMeta(name=pod.metadata.name)
    body   = client.V1Binding(target=target, metadata=meta)
    v1.create_namespaced_binding(namespace=pod.metadata.namespace, body=body)
    log.info(f"[bind] {pod.metadata.namespace}/{pod.metadata.name} → {node_name}")


def run():
    w = watch.Watch()
    for event in w.stream(v1.list_pod_for_all_namespaces, timeout_seconds=0):
        pod: client.V1Pod = event["object"]
        if pod.metadata.deletion_timestamp:
            continue
        if pod.spec.scheduler_name != SCHEDULER_NAME:
            continue
        if pod.spec.node_name:
            continue

        log.info(f"[event] 워크로드 감지 → {pod.metadata.namespace}/{pod.metadata.name}")

        nodes = v1.list_node(label_selector="kubernetes.io/arch=arm64").items
        if not nodes:
            log.error("[filter] ARM 워커 없음 → 스케줄 불가")
            continue
        log.debug(f"[filter] ARM 워커 {len(nodes)}개 발견")
        log.debug(f"[Policy-Engine] MALE 정책 중 에너지 최우선 적용")

        node_map = make_node_map(nodes)
        tbl = {n: {"wh": v['wh'], "pose": v['pose']} for n, v in node_map.items()}
        log.debug(f"[score] 노드 상태 테이블 → {json.dumps(tbl, default=str)}")

        choice = choose_node(node_map, nodes)
        log.info(f"[policy-MALE] 선택 노드: {choice}")

        try:
            bind_pod(pod, choice)
        except Exception as e:
            pass


if __name__ == "__main__":
    log.info("=== SDI Scheduler(MALE) 시작 ===")
    while True:
        try:
            run()
        except Exception as e:
            log.exception(f"[main] 예외 발생 → {e}")
            time.sleep(5)
