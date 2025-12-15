# SDI Edge Cluster Scheduler

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

SDI Edge Cluster Scheduler는 Kubernetes의 커스텀 스케줄러로, MALE(Multi-Agent Learning Environment) 정책 기반 에너지 최우선 스케줄링을 수행합니다.

### 주요 특징

- **에너지 기반 스케줄링**: InfluxDB에서 노드의 배터리 상태(Wh)를 조회하여 가장 에너지가 높은 노드를 선택
- **ARM64 아키텍처 필터링**: `kubernetes.io/arch=arm64` 레이블을 가진 노드만 스케줄링 대상으로 선택
- **실시간 모니터링**: InfluxDB의 메트릭 데이터를 실시간으로 조회하여 스케줄링 결정
- **자동 복구**: 예외 발생 시 자동으로 재시도하는 안정적인 구조

---

## 폴더 구조

```
src/scheduler/
├── README.md                    # 이 문서
├── Dockerfile                    # Docker 이미지 빌드 파일
├── scheduler.py                 # 스케줄러 메인 코드
├── requirements.txt             # Python 의존성 패키지
└── SDI-Scheduler-deploy.yaml    # Kubernetes 배포 매니페스트
```

### 파일 설명

- **`scheduler.py`**: 스케줄러의 핵심 로직이 포함된 메인 파일
  - Kubernetes API를 통한 Pod 감지 및 바인딩
  - InfluxDB를 통한 노드 메트릭 조회
  - MALE 정책 기반 노드 선택 로직

- **`requirements.txt`**: Python 패키지 의존성
  - `kubernetes==29.0.0`: Kubernetes Python 클라이언트
  - `influxdb-client==1.41.0`: InfluxDB 클라이언트

- **`Dockerfile`**: Docker 이미지 빌드를 위한 파일
  - Python 3.12 기반 이미지
  - 의존성 설치 및 소스 코드 복사

- **`SDI-Scheduler-deploy.yaml`**: Kubernetes 배포 매니페스트
  - ServiceAccount, ClusterRole, ClusterRoleBinding
  - ConfigMap, Secret
  - Deployment

---

## 기능 설명

### 스케줄링 프로세스

1. **Pod 감지**: Kubernetes Watch API를 통해 `schedulerName: sdi-scheduler`로 지정된 Pod 감지
2. **노드 필터링**: ARM64 아키텍처 노드만 필터링
3. **메트릭 조회**: InfluxDB에서 각 노드의 배터리 상태(Wh)와 위치 정보 조회
4. **노드 선택**: 배터리 에너지가 가장 높은 노드 선택 (MALE 정책)
5. **Pod 바인딩**: 선택된 노드에 Pod 바인딩

### 주요 함수

- `latest_wh(bot: str)`: 노드의 최신 배터리 에너지(Wh) 조회
- `latest_pose(bot: str)`: 노드의 최신 위치 정보(x, y) 조회
- `make_node_map(nodes)`: 노드별 메트릭 정보 맵 생성
- `choose_node(node_map, nodes)`: MALE 정책 기반 최적 노드 선택
- `bind_pod(pod, node_name)`: Pod를 선택된 노드에 바인딩

---

## 개발 환경 설정

### 필수 요구사항

- Python 3.8 이상
- Kubernetes 클러스터 접근 권한
- InfluxDB 접근 권한
- Docker (이미지 빌드용)

### 의존성 설치

```bash
cd src/scheduler
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
export INFLUX_URL="http://influxdb.tbot-monitoring.svc.cluster.local:8086"
export INFLUX_TOKEN="your-influxdb-token"
export INFLUX_ORG="keti"
export INFLUX_BUCKET="turtlebot"
```

### 2. Kubernetes 클러스터 접근 설정

로컬에서 개발할 경우, Kubernetes 클러스터에 접근할 수 있도록 kubeconfig를 설정해야 합니다:

```bash
# kubeconfig 파일이 있는 경우
export KUBECONFIG=/path/to/kubeconfig

# 또는 kubectl이 이미 설정된 경우
kubectl config view
```

**주의**: `scheduler.py`는 현재 `config.load_incluster_config()`만 사용하므로, 클러스터 내부에서만 실행 가능합니다. 로컬 개발을 위해서는 코드 수정이 필요합니다.

### 3. 코드 수정 (로컬 개발용)

로컬에서 테스트하려면 `scheduler.py`의 35번째 줄을 다음과 같이 수정:

```python
# 기존
config.load_incluster_config()

# 수정 후
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()
```

### 4. 실행

```bash
python3 scheduler.py
```

---

## 개발 및 배포 순서도

### 전체 워크플로우

```
1. 개발 (코드 수정)
   ↓
2. Docker 이미지 빌드
   ↓
3. Docker 이미지 푸시
   ↓
4. Containerd에 Import (Kind/K3s용)
   ↓
5. 배포/업데이트 (kubectl rollout restart)
   ↓
6. 확인 (로그 체크)
```

### 상세 단계별 가이드

#### 1. 코드 수정

스케줄러 코드를 수정합니다:

```bash
# 스케줄러 코드 수정
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/scheduler/scheduler.py

# 또는 다른 에디터 사용
nano /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/scheduler/scheduler.py
```

**주요 수정 사항 예시:**
- 스케줄링 로직 변경
- InfluxDB 쿼리 수정
- 로깅 레벨 조정
- 에러 처리 개선

#### 2. Docker 이미지 빌드 (필수!)

수정된 코드로 Docker 이미지를 빌드합니다:

```bash
# 스케줄러 디렉토리로 이동
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/scheduler

# Docker 이미지 빌드
docker build -t <이미지 이름> .

# 예시:
docker build -t ketidevit2/sdi-scheduler:1.1 .
# 또는
docker build -t ketidevit2/sdi-scheduler:1.2 .
```

**이미지 태그 규칙:**
- 버전 업데이트: `1.1` → `1.2` → `1.3`
- 개발 버전: `1.1-dev`, `1.1-test`
- 날짜 기반: `1.1-20241201`

**빌드 확인:**
```bash
# 빌드된 이미지 확인
docker images | grep sdi-scheduler

# 이미지 상세 정보 확인
docker inspect ketidevit2/sdi-scheduler:1.1
```

#### 3. Docker 이미지 푸시 (필수!)

빌드한 이미지를 레지스트리에 푸시합니다:

```bash
# Docker Hub에 푸시
docker push <이미지 이름>

# 예시:
docker push ketidevit2/sdi-scheduler:1.1
```

**프라이빗 레지스트리 사용 시:**
```bash
# 레지스트리 로그인
docker login your-registry.com

# 태그 변경
docker tag ketidevit2/sdi-scheduler:1.1 your-registry.com/sdi-scheduler:1.1

# 푸시
docker push your-registry.com/sdi-scheduler:1.1
```

**오프라인 환경 (이미지 저장):**
```bash
# 이미지를 tar 파일로 저장
docker save ketidevit2/sdi-scheduler:1.1 -o /tmp/sdi-scheduler-1.1.tar

# 또는 gzip 압축
docker save ketidevit2/sdi-scheduler:1.1 | gzip > /tmp/sdi-scheduler-1.1.tar.gz
```

#### 4. Containerd에 Import (Kind/K3s용, 필수!)

K3s나 Kind 같은 containerd 기반 클러스터에서는 이미지를 직접 import해야 합니다:

```bash
# Docker 이미지를 tar 파일로 저장
docker save ketidevit2/sdi-scheduler:1.1 -o /tmp/sdi-scheduler.tar

# Containerd에 import (K3s/Kind용)
sudo ctr -n k8s.io images import /tmp/sdi-scheduler.tar

# 또는 압축 해제 후 import
gunzip -c /tmp/sdi-scheduler.tar.gz | sudo ctr -n k8s.io images import -
```

**이미지 확인:**
```bash
# Containerd에 import된 이미지 확인
sudo ctr -n k8s.io images list | grep sdi-scheduler

# 이미지 상세 정보
sudo ctr -n k8s.io images inspect ketidevit2/sdi-scheduler:1.1
```

**주의사항:**
- K3s/Kind 환경에서는 반드시 이 단계를 수행해야 합니다
- 일반 Kubernetes 클러스터(Docker 기반)에서는 이 단계가 필요 없습니다

#### 5. 배포 매니페스트 업데이트 (선택사항)

새로운 이미지 태그를 사용하는 경우 배포 매니페스트를 업데이트합니다:

```bash
# 배포 매니페스트 수정
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/scheduler/SDI-Scheduler-deploy.yaml

# 이미지 태그 변경 예시:
# image: ketidevit2/sdi-scheduler:1.1  →  image: ketidevit2/sdi-scheduler:1.2
```

**또는 kubectl로 직접 이미지 태그 변경:**
```bash
# Deployment의 이미지 태그 직접 변경
kubectl set image deployment/sdi-scheduler \
  scheduler=ketidevit2/sdi-scheduler:1.2 \
  -n kube-system
```

#### 6. Kubernetes 배포/업데이트 (필수!)

스케줄러를 배포하거나 업데이트합니다:

**초기 배포:**
```bash
# 배포 매니페스트 적용
kubectl apply -f /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/scheduler/SDI-Scheduler-deploy.yaml

# 또는 deploy 디렉토리에서
kubectl apply -f /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/deploy/scheduler/SDI-Scheduler-deploy.yaml
```

**업데이트 (롤링 재시작):**
```bash
# Deployment 롤링 재시작 (가장 안전한 방법)
kubectl rollout restart deployment/sdi-scheduler -n kube-system

# 또는 이미지 태그 변경 후
kubectl set image deployment/sdi-scheduler \
  scheduler=ketidevit2/sdi-scheduler:1.2 \
  -n kube-system
```

**배포 상태 확인:**
```bash
# Deployment 상태 확인
kubectl get deployment sdi-scheduler -n kube-system

# Pod 상태 확인
kubectl get pods -n kube-system | grep sdi-scheduler

# 롤아웃 상태 확인
kubectl rollout status deployment/sdi-scheduler -n kube-system
```

#### 7. 확인 (로그 체크)

스케줄러가 정상적으로 동작하는지 확인합니다:

```bash
# 실시간 로그 확인
kubectl logs -n kube-system -l app=sdi-scheduler -f

# 최근 로그 확인 (SDI 관련만)
kubectl logs -n kube-system -l app=sdi-scheduler --tail=50 | grep -E "(SDI|bind|policy-MALE|event)"

# Pod 이벤트 확인
kubectl describe pod -n kube-system -l app=sdi-scheduler

# 스케줄러가 정상 시작되었는지 확인
kubectl logs -n kube-system -l app=sdi-scheduler --tail=20 | grep "SDI Scheduler"
```

**성공적인 시작 로그 예시:**
```
2024-12-01 14:00:00 INFO [scheduler] === SDI Scheduler(MALE) 시작 ===
2024-12-01 14:00:01 DEBUG [scheduler] [filter] ARM 워커 3개 발견
```

**스케줄링 동작 확인:**
```bash
# 테스트 Pod 생성
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: sdi-test-pod
spec:
  schedulerName: sdi-scheduler
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
EOF

# Pod가 스케줄링되었는지 확인
kubectl get pod sdi-test-pod -o wide

# 스케줄러 로그에서 바인딩 확인
kubectl logs -n kube-system -l app=sdi-scheduler | grep "bind"
```

### 전체 스크립트 예시

한 번에 실행하는 스크립트 예시:

```bash
#!/bin/bash
# 스케줄러 개발 및 배포 스크립트

set -e

# 변수 설정
IMAGE_NAME="ketidevit2/sdi-scheduler"
VERSION="1.2"
SCHEDULER_DIR="/root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/scheduler"
NAMESPACE="kube-system"

echo "=== 1. 코드 수정 확인 ==="
cd $SCHEDULER_DIR
git status || echo "Git이 없거나 변경사항 확인 불가"

echo "=== 2. Docker 이미지 빌드 ==="
docker build -t ${IMAGE_NAME}:${VERSION} .

echo "=== 3. Docker 이미지 푸시 ==="
docker push ${IMAGE_NAME}:${VERSION}

echo "=== 4. Containerd에 Import (K3s/Kind용) ==="
docker save ${IMAGE_NAME}:${VERSION} -o /tmp/sdi-scheduler.tar
sudo ctr -n k8s.io images import /tmp/sdi-scheduler.tar
rm /tmp/sdi-scheduler.tar

echo "=== 5. 배포 업데이트 ==="
kubectl set image deployment/sdi-scheduler \
  scheduler=${IMAGE_NAME}:${VERSION} \
  -n ${NAMESPACE}

echo "=== 6. 롤아웃 상태 확인 ==="
kubectl rollout status deployment/sdi-scheduler -n ${NAMESPACE}

echo "=== 7. 로그 확인 ==="
sleep 5
kubectl logs -n ${NAMESPACE} -l app=sdi-scheduler --tail=20 | grep -E "(SDI|시작)"

echo "=== 배포 완료! ==="
```

### 빠른 업데이트 (이미지만 변경)

이미 배포된 상태에서 코드만 수정하고 빠르게 업데이트하는 경우:

```bash
# 1. 이미지 빌드 및 푸시
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/scheduler
docker build -t ketidevit2/sdi-scheduler:1.2 .
docker push ketidevit2/sdi-scheduler:1.2

# 2. Containerd import (K3s/Kind)
docker save ketidevit2/sdi-scheduler:1.2 -o /tmp/sdi-scheduler.tar
sudo ctr -n k8s.io images import /tmp/sdi-scheduler.tar

# 3. 롤링 재시작
kubectl rollout restart deployment/sdi-scheduler -n kube-system

# 4. 로그 확인
kubectl logs -n kube-system -l app=sdi-scheduler -f
```

---

## Docker 이미지 빌드

### Dockerfile 생성

`src/scheduler/` 디렉토리에 `Dockerfile` 생성:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 의존성 파일 복사
COPY requirements.txt .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY scheduler.py .

# 실행 권한 부여
RUN chmod +x scheduler.py

# 실행
CMD ["python3", "scheduler.py"]
```

### 이미지 빌드

```bash
cd src/scheduler

# 이미지 빌드
docker build -t ketidevit2/sdi-scheduler:1.1 .

# 태그 확인
docker images | grep sdi-scheduler
```

### 이미지 푸시 (선택사항)

```bash
# Docker Hub에 푸시
docker push ketidevit2/sdi-scheduler:1.1

# 또는 프라이빗 레지스트리에 푸시
docker tag ketidevit2/sdi-scheduler:1.1 your-registry/sdi-scheduler:1.1
docker push your-registry/sdi-scheduler:1.1
```

---

## Kubernetes 배포

### 1. InfluxDB 토큰 확인

InfluxDB 토큰을 확인하고 `SDI-Scheduler-deploy.yaml`의 Secret 부분을 수정:

```yaml
# 4) InfluxDB Secret (토큰)
apiVersion: v1
kind: Secret
metadata:
  name: sdi-influx-creds
  namespace: kube-system
type: Opaque
stringData:
  token: <여기에 실제 토큰 입력>
```

### 2. 배포 매니페스트 확인

`SDI-Scheduler-deploy.yaml` 파일을 확인하고 필요시 수정:

- 이미지 태그: `ketidevit2/sdi-scheduler:1.1`
- InfluxDB URL: `http://influxdb.tbot-monitoring.svc.cluster.local:8086`
- InfluxDB Org: `keti`
- InfluxDB Bucket: `turtlebot`

### 3. 배포 실행

```bash
# 배포 적용
kubectl apply -f SDI-Scheduler-deploy.yaml

# 배포 상태 확인
kubectl get deployment sdi-scheduler -n kube-system

# Pod 상태 확인
kubectl get pods -n kube-system | grep sdi-scheduler

# 로그 확인
kubectl logs -n kube-system -l app=sdi-scheduler -f
```

### 4. 배포 확인

```bash
# ServiceAccount 확인
kubectl get serviceaccount sdi-scheduler -n kube-system

# ClusterRole 확인
kubectl get clusterrole sdi-scheduler

# ClusterRoleBinding 확인
kubectl get clusterrolebinding sdi-scheduler

# ConfigMap 확인
kubectl get configmap monitoring-metric-data-cm -n kube-system

# Secret 확인
kubectl get secret sdi-influx-creds -n kube-system
```

---

## 테스트 방법

### 1. 테스트 Pod 생성

테스트용 Pod를 생성하여 스케줄러가 정상 동작하는지 확인:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sdi-test-pod
spec:
  schedulerName: sdi-scheduler   # 중요: sdi-scheduler 지정
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
```

```bash
# 테스트 Pod 생성
kubectl apply -f test-pod.yaml

# Pod 상태 확인
kubectl get pod sdi-test-pod -o wide

# 스케줄러 로그에서 바인딩 확인
kubectl logs -n kube-system -l app=sdi-scheduler | grep "bind"
```

### 2. 스케줄러 로그 확인

```bash
# 실시간 로그 확인
kubectl logs -n kube-system -l app=sdi-scheduler -f

# 최근 100줄 로그 확인
kubectl logs -n kube-system -l app=sdi-scheduler --tail=100
```

### 3. 노드 메트릭 확인

InfluxDB에 노드의 배터리 및 위치 정보가 정상적으로 저장되어 있는지 확인:

```bash
# InfluxDB에 접속하여 쿼리 실행
# 또는 스케줄러 로그에서 메트릭 조회 결과 확인
kubectl logs -n kube-system -l app=sdi-scheduler | grep "score"
```

---

## 트러블슈팅

### 1. Pod가 스케줄링되지 않음

**증상**: Pod가 `Pending` 상태로 유지됨

**확인 사항**:
- Pod의 `schedulerName`이 `sdi-scheduler`로 설정되어 있는지 확인
- 스케줄러 Pod가 정상 실행 중인지 확인: `kubectl get pods -n kube-system | grep sdi-scheduler`
- 스케줄러 로그 확인: `kubectl logs -n kube-system -l app=sdi-scheduler`

**해결 방법**:
```bash
# 스케줄러 재시작
kubectl rollout restart deployment sdi-scheduler -n kube-system

# 스케줄러 로그 확인
kubectl logs -n kube-system -l app=sdi-scheduler -f
```

### 2. InfluxDB 연결 실패

**증상**: 로그에 "배터리 조회 실패" 또는 "위치 조회 실패" 메시지

**확인 사항**:
- InfluxDB 서비스가 정상 실행 중인지: `kubectl get svc -n tbot-monitoring | grep influxdb`
- InfluxDB 토큰이 올바른지: `kubectl get secret sdi-influx-creds -n kube-system -o jsonpath='{.data.token}' | base64 -d`
- 네트워크 연결 확인: `kubectl exec -n kube-system -l app=sdi-scheduler -- curl -I http://influxdb.tbot-monitoring.svc.cluster.local:8086`

**해결 방법**:
```bash
# Secret 재생성
kubectl delete secret sdi-influx-creds -n kube-system
kubectl create secret generic sdi-influx-creds \
  --from-literal=token='your-token' \
  -n kube-system

# 스케줄러 재시작
kubectl rollout restart deployment sdi-scheduler -n kube-system
```

### 3. 권한 오류

**증상**: "Forbidden" 또는 "Unauthorized" 에러

**확인 사항**:
- ServiceAccount가 올바르게 생성되었는지: `kubectl get serviceaccount sdi-scheduler -n kube-system`
- ClusterRole과 ClusterRoleBinding이 올바르게 설정되었는지 확인

**해결 방법**:
```bash
# RBAC 리소스 재생성
kubectl apply -f SDI-Scheduler-deploy.yaml

# 권한 확인
kubectl auth can-i create pods/binding --as=system:serviceaccount:kube-system:sdi-scheduler
```

### 4. ARM64 노드를 찾을 수 없음

**증상**: 로그에 "ARM 워커 없음 → 스케줄 불가" 메시지

**확인 사항**:
- ARM64 노드가 클러스터에 존재하는지: `kubectl get nodes -l kubernetes.io/arch=arm64`
- 노드 레이블 확인: `kubectl get nodes --show-labels`

**해결 방법**:
- ARM64 노드가 없는 경우, 스케줄러 코드에서 아키텍처 필터를 제거하거나 수정

### 5. 이미지 Pull 실패

**증상**: Pod가 `ImagePullBackOff` 상태

**확인 사항**:
- 이미지가 레지스트리에 존재하는지 확인
- 이미지 Pull 정책 확인: `imagePullPolicy: IfNotPresent` 또는 `Always`

**해결 방법**:
```bash
# 이미지를 로컬에 로드 (오프라인 환경)
docker load -i sdi-scheduler-1.1.tar

# 또는 이미지 태그 수정 후 재배포
```

---

## 참고 자료

- [Kubernetes Scheduler Extensions](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/)
- [Kubernetes Python Client](https://github.com/kubernetes-client/python)
- [InfluxDB Python Client](https://github.com/influxdata/influxdb-client-python)
- [MALE Policy Engine Documentation](../README.md)

---

## 변경 이력

- **v1.1**: 초기 버전 - MALE 정책 기반 에너지 최우선 스케줄링 구현
- **v1.0**: 기본 스케줄러 구현

---

## 문의

문제가 발생하거나 개선 사항이 있으면 이슈를 등록해주세요.

