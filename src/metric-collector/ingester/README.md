# SDI Edge Cluster Metrics Ingester

## 📋 목차

1. [개요](#개요)
2. [폴더 구조](#폴더-구조)
3. [기능 설명](#기능-설명)
4. [개발 환경 설정](#개발-환경-설정)
5. [로컬 개발 방법](#로컬-개발-방법)
6. [개발 및 배포 순서도](#개발-및-배포-순서도)
7. [Docker 이미지 빌드](#docker-이미지-빌드)
8. [Kubernetes 배포](#kubernetes-배포)
9. [테스트 방법](#테스트-방법)
10. [트러블슈팅](#트러블슈팅)

---

## 개요

SDI Edge Cluster Metrics Ingester는 RabbitMQ에서 수신한 텔레메트리 메시지를 InfluxDB에 저장하는 데이터 파이프라인 컴포넌트입니다.

### 주요 특징

- **RabbitMQ 메시지 수신**: `turtlebot.telemetry` 큐에서 메시지 수신
- **데이터 파싱**: JSON 형식의 텔레메트리 데이터 파싱
- **InfluxDB 저장**: 배터리 및 포즈 데이터를 InfluxDB에 저장
- **에러 처리**: 처리 불가능한 메시지는 폐기하여 큐 블로킹 방지
- **배치 처리**: 한 번에 최대 20개의 메시지만 처리하도록 제한

---

## 폴더 구조

```
src/metric-collector/ingester/
├── README.md                    # 이 문서
├── Dockerfile                    # Docker 이미지 빌드 파일
├── ingester.py                  # Ingester 메인 코드
├── requirements.txt             # Python 의존성 패키지
└── Metric-Collector-deploy.yaml # Kubernetes 배포 매니페스트
```

### 파일 설명

- **`ingester.py`**: Ingester의 핵심 로직이 포함된 메인 파일
  - RabbitMQ 연결 및 메시지 수신
  - JSON 메시지 파싱 및 검증
  - InfluxDB에 데이터 포인트 작성
  - 배터리 및 포즈 데이터 처리

- **`requirements.txt`**: Python 패키지 의존성
  - `pika==1.3.2`: RabbitMQ Python 클라이언트
  - `influxdb-client==1.41.0`: InfluxDB 클라이언트

- **`Dockerfile`**: Docker 이미지 빌드를 위한 파일
  - Python 3.12 기반 이미지
  - 의존성 설치 및 소스 코드 복사

- **`Metric-Collector-deploy.yaml`**: Kubernetes 배포 매니페스트
  - RabbitMQ Deployment 및 Service
  - InfluxDB StatefulSet 및 Service
  - Ingester Deployment
  - Secret 및 ConfigMap

---

## 기능 설명

### 데이터 처리 프로세스

1. **메시지 수신**: RabbitMQ의 `turtlebot.telemetry` 큐에서 메시지 수신
2. **메시지 검증**: `type` 필드가 `telemetry`인지 확인
3. **데이터 파싱**: JSON 메시지에서 배터리 및 포즈 데이터 추출
4. **타임스탬프 변환**: 나노초 단위 타임스탬프를 UTC datetime으로 변환
5. **InfluxDB 저장**: 배터리 및 포즈 데이터를 각각의 Point로 변환하여 저장

### 처리하는 데이터 타입

#### 배터리 데이터 (`battery`)
- `percentage`: 배터리 잔량 (%)
- `voltage`: 전압 (V)
- `wh`: 에너지 (Wh)

#### 포즈 데이터 (`pose`)
- `x`: X 좌표
- `y`: Y 좌표

### 주요 함수

- `cb(ch, method, props, body)`: RabbitMQ 메시지 콜백 함수
  - 메시지 파싱 및 검증
  - 배터리 및 포즈 데이터 추출
  - InfluxDB에 데이터 포인트 작성
  - 메시지 ACK/NACK 처리

---

## 개발 환경 설정

### 필수 요구사항

- Python 3.8 이상
- RabbitMQ 접근 권한
- InfluxDB 접근 권한
- Docker (이미지 빌드용)

### 의존성 설치

```bash
cd src/ingester
pip3 install -r requirements.txt
```

또는 가상환경 사용:

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

---

## 로컬 개발 방법

### 1. 환경 변수 설정

```bash
export RABBITMQ_HOST="localhost"
export RABBITMQ_USER="keti"
export RABBITMQ_PASS="opensdi123"
export INFLUX_URL="http://localhost:8086"
export INFLUX_TOKEN="your-influxdb-token"
export INFLUX_ORG="keti"
export INFLUX_BUCKET="turtlebot"
```

### 2. RabbitMQ 및 InfluxDB 실행

로컬에서 테스트하려면 RabbitMQ와 InfluxDB가 실행 중이어야 합니다:

```bash
# RabbitMQ 실행 (Docker 예시)
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=keti \
  -e RABBITMQ_DEFAULT_PASS=opensdi123 \
  rabbitmq:3-management-alpine

# InfluxDB 실행 (Docker 예시)
docker run -d --name influxdb \
  -p 8086:8086 \
  -e DOCKER_INFLUXDB_INIT_MODE=setup \
  -e DOCKER_INFLUXDB_INIT_BUCKET=turtlebot \
  -e DOCKER_INFLUXDB_INIT_ORG=keti \
  -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=your-token \
  influxdb:2.7
```

### 3. 실행

```bash
python3 ingester.py
```

---

## 개발 및 배포 순서도

### 1). 개발 및 배포 순서

```markdown
1. 개발 (코드 수정)
   ↓
2. Docker 이미지 빌드
   ↓
3. Docker 이미지 푸시
   ↓
4. Containerd에 Import (Kind/K3s용) -> 외부망 열려있으면 자동으로 가능
   ↓
5. 배포/업데이트 (kubectl rollout restart)
   ↓
6. 확인 (로그 체크)
```

### 2). 개발 및 배포 자세한 방법

```bash
# 1. 코드 수정
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/metric-collector/ingester/ingester.py

# 2. Docker 이미지 빌드 (필수!)
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/metric-collector/ingester

docker build -t <이미지 이름> .  # Ex) docker build -t ketidevit2/rabbit-influx-ingester:0.8 .

# 3. Docker 이미지 푸시 (필수!)
docker push <이미지 이름>  # Ex) docker push ketidevit2/rabbit-influx-ingester:0.8

# 4. Containerd에 Import (K3s에서 필수!)
#docker save ketidevit2/rabbit-influx-ingester:0.8 -o /tmp/ingester.tar

#sudo ctr -n k8s.io images import /tmp/ingester.tar

# 5. Kubernetes 배포/업데이트 (필수!)
kubectl rollout restart deployment/metrics-ingester -n tbot-monitoring

# 6. 확인
kubectl logs -n tbot-monitoring -l app=ingester --tail=20 | grep -E "(Starting|ingest)"
```

---

## Docker 이미지 빌드

### Dockerfile 생성

`src/metric-collector/ingester/` 디렉토리에 `Dockerfile` 생성:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 의존성 파일 복사
COPY requirements.txt .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY ingester.py .

# 실행 권한 부여
RUN chmod +x ingester.py

# 실행
CMD ["python3", "ingester.py"]
```

### 이미지 빌드

```bash
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/metric-collector/ingester

# 이미지 빌드
docker build -t ketidevit2/rabbit-influx-ingester:0.8 .

# 태그 확인
docker images | grep ingester
```

### 이미지 푸시 (선택사항)

```bash
# Docker Hub에 푸시
docker push ketidevit2/rabbit-influx-ingester:0.8

# 또는 프라이빗 레지스트리에 푸시
docker tag ketidevit2/rabbit-influx-ingester:0.8 your-registry/rabbit-influx-ingester:0.8
docker push your-registry/rabbit-influx-ingester:0.8
```

---

## Kubernetes 배포

### 1. 배포 매니페스트 확인

Ingester는 `Metric-Collector-deploy.yaml` 파일에 포함되어 있습니다:

```yaml
# ---------- Ingester ----------
apiVersion: apps/v1
kind: Deployment
metadata: { name: metrics-ingester, namespace: tbot-monitoring }
spec:
  selector: { matchLabels: { app: ingester } }
  template:
    metadata: { labels: { app: ingester } }
    spec:
      nodeSelector: { kubernetes.io/arch: amd64 }
      containers:
      - name: ingester
        image: ketidevit2/rabbit-influx-ingester:0.8
        env:
        - { name: RABBITMQ_HOST, value: metric-collector.tbot-monitoring.svc.cluster.local }
        - name: RABBITMQ_USER
          valueFrom: { secretKeyRef: { name: rabbitmq-creds, key: user } }
        - name: RABBITMQ_PASS
          valueFrom: { secretKeyRef: { name: rabbitmq-creds, key: pass } }
        - { name: INFLUX_URL,  value: http://influxdb.tbot-monitoring.svc.cluster.local:8086 }
        - name: INFLUX_TOKEN
          valueFrom: { secretKeyRef: { name: influxdb-creds, key: token } }
        - { name: INFLUX_ORG,    value: keti }
        - { name: INFLUX_BUCKET, value: turtlebot }
```

### 2. 배포 실행

```bash
# 배포 적용 (Metric-Collector-deploy.yaml에 포함되어 있음)
kubectl apply -f /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/metric-collector/ingester/Metric-Collector-deploy.yaml

# 또는 다른 위치의 배포 파일 사용
kubectl apply -f /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/deploy/metric-collector/Metric-Collector-deploy.yaml

# 또는
kubectl apply -f /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/scripts/etri-setup/k3s/SDI-Orchestration/Metric-Collector/Metric-Collector-deploy.yaml

# 배포 상태 확인
kubectl get deployment metrics-ingester -n tbot-monitoring

# Pod 상태 확인
kubectl get pods -n tbot-monitoring | grep ingester

# 로그 확인
kubectl logs -n tbot-monitoring -l app=ingester -f
```

### 3. 배포 확인

```bash
# Deployment 확인
kubectl get deployment metrics-ingester -n tbot-monitoring

# Pod 확인
kubectl get pods -n tbot-monitoring -l app=ingester

# Secret 확인
kubectl get secret rabbitmq-creds -n tbot-monitoring
kubectl get secret influxdb-creds -n tbot-monitoring
```

---

## 테스트 방법

### 1. 테스트 메시지 전송

RabbitMQ에 테스트 메시지를 전송하여 Ingester가 정상 동작하는지 확인:

```bash
# RabbitMQ Management UI 접속
# http://<node-ip>:31672 (NodePort)
# 또는 kubectl port-forward 사용
kubectl port-forward -n tbot-monitoring svc/metric-collector 15672:15672

# Python으로 테스트 메시지 전송
python3 <<EOF
import pika
import json
import time

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='localhost',
        port=5672,
        credentials=pika.PlainCredentials('keti', 'opensdi123')
    )
)
channel = connection.channel()
channel.queue_declare(queue='turtlebot.telemetry', durable=True)

message = {
    "type": "telemetry",
    "ts": int(time.time() * 1e9),
    "bot": "test-bot",
    "battery": {
        "percentage": 80.0,
        "voltage": 12.6,
        "wh": 50.0
    },
    "pose": {
        "x": 1.5,
        "y": 2.3
    }
}

channel.basic_publish(
    exchange='',
    routing_key='turtlebot.telemetry',
    body=json.dumps(message),
    properties=pika.BasicProperties(delivery_mode=2)  # 메시지 영속성
)

print("메시지 전송 완료")
connection.close()
EOF
```

### 2. Ingester 로그 확인

```bash
# 실시간 로그 확인
kubectl logs -n tbot-monitoring -l app=ingester -f

# 최근 100줄 로그 확인
kubectl logs -n tbot-monitoring -l app=ingester --tail=100
```

### 3. InfluxDB 데이터 확인

InfluxDB에 데이터가 정상적으로 저장되었는지 확인:

```bash
# InfluxDB에 접속하여 쿼리 실행
# 또는 InfluxDB UI에서 확인
# http://<node-ip>:32086
```

---

## 트러블슈팅

### 1. RabbitMQ 연결 실패

**증상**: 로그에 "Connection refused" 또는 "Authentication failed" 에러

**확인 사항**:
- RabbitMQ 서비스가 정상 실행 중인지: `kubectl get pods -n tbot-monitoring | grep rabbitmq`
- RabbitMQ 서비스 확인: `kubectl get svc -n tbot-monitoring | grep metric-collector`
- Secret 확인: `kubectl get secret rabbitmq-creds -n tbot-monitoring -o yaml`

**해결 방법**:
```bash
# Secret 재생성
kubectl delete secret rabbitmq-creds -n tbot-monitoring
kubectl create secret generic rabbitmq-creds \
  --from-literal=user='keti' \
  --from-literal=pass='opensdi123' \
  -n tbot-monitoring

# Ingester 재시작
kubectl rollout restart deployment/metrics-ingester -n tbot-monitoring
```

### 2. InfluxDB 연결 실패

**증상**: 로그에 "ingest error" 또는 "Connection refused" 에러

**확인 사항**:
- InfluxDB 서비스가 정상 실행 중인지: `kubectl get pods -n tbot-monitoring | grep influxdb`
- InfluxDB 서비스 확인: `kubectl get svc -n tbot-monitoring | grep influxdb`
- Secret 확인: `kubectl get secret influxdb-creds -n tbot-monitoring -o yaml`
- 네트워크 연결 확인: `kubectl exec -n tbot-monitoring -l app=ingester -- curl -I http://influxdb.tbot-monitoring.svc.cluster.local:8086`

**해결 방법**:
```bash
# Secret 재생성
kubectl delete secret influxdb-creds -n tbot-monitoring
kubectl create secret generic influxdb-creds \
  --from-literal=token='your-token' \
  -n tbot-monitoring

# Ingester 재시작
kubectl rollout restart deployment/metrics-ingester -n tbot-monitoring
```

### 3. 메시지가 처리되지 않음

**증상**: RabbitMQ에 메시지가 쌓이지만 Ingester가 처리하지 않음

**확인 사항**:
- 큐가 정상적으로 선언되었는지 확인
- 메시지 형식이 올바른지 확인 (`type: "telemetry"`)
- Ingester 로그에서 에러 확인

**해결 방법**:
```bash
# Ingester 로그 확인
kubectl logs -n tbot-monitoring -l app=ingester --tail=100

# 큐 상태 확인 (RabbitMQ Management UI)
# http://<node-ip>:31672
```

### 4. 메시지 형식 오류

**증상**: 로그에 "Unknown message type" 경고

**원인**: `type` 필드가 `telemetry`가 아닌 메시지

**해결 방법**:
- 메시지 전송 시 `type: "telemetry"` 필드가 포함되어 있는지 확인
- 올바른 형식의 메시지만 전송하도록 수정

### 5. 이미지 Pull 실패

**증상**: Pod가 `ImagePullBackOff` 상태

**확인 사항**:
- 이미지가 레지스트리에 존재하는지 확인
- 이미지 Pull 정책 확인

**해결 방법**:
```bash
# 이미지를 로컬에 로드 (오프라인 환경)
docker load -i ingester-0.8.tar

# 또는 이미지 태그 수정 후 재배포
kubectl set image deployment/metrics-ingester \
  ingester=ketidevit2/rabbit-influx-ingester:0.8 \
  -n tbot-monitoring
```

---

## 참고 자료

- [RabbitMQ Python Client (pika)](https://pika.readthedocs.io/)
- [InfluxDB Python Client](https://github.com/influxdata/influxdb-client-python)
- [RabbitMQ Management Guide](https://www.rabbitmq.com/management.html)
- [InfluxDB Documentation](https://docs.influxdata.com/influxdb/)

---

## 변경 이력

- **v0.8**: 현재 버전 - RabbitMQ에서 InfluxDB로 데이터 파이프라인 구현
- **v0.7**: 초기 버전

---

## 문의

문제가 발생하거나 개선 사항이 있으면 이슈를 등록해주세요.

