# YOLO 컴포넌트 개발 및 배포 가이드

## 📋 목차

1. [개요](#개요)
2. [컴포넌트 구조](#컴포넌트-구조)
3. [Backbone 개발 및 배포](#backbone-개발-및-배포)
4. [Neck-Head-Slim 개발 및 배포](#neck-head-slim-개발-및-배포)
5. [Server 개발 및 배포](#server-개발-및-배포)
6. [YOLOv5 개발 및 배포](#yolov5-개발-및-배포)

---

## 개요

YOLO 컴포넌트는 YOLOv5 모델을 레이어별로 분할하여 실행하는 분산 처리 시스템입니다.

### 컴포넌트 구성

- **Backbone**: YOLO 모델의 백본 네트워크 처리
- **Neck-Head-Slim**: YOLO 모델의 Neck과 Head 부분 처리
- **Server**: 이미지 서버 (FastAPI 기반)
- **YOLOv5**: YOLOv5 기본 모델

---

## 컴포넌트 구조

```
src/yolo/
├── backbone/              # Backbone 컴포넌트
│   └── pod_sync/          # Pod 동기화 코드
├── neck-head-slim/        # Neck-Head 컴포넌트
│   └── app/               # 애플리케이션 코드
├── server/                # 이미지 서버
│   └── pod_sync/          # Pod 동기화 코드
└── yolov5/                # YOLOv5 기본 모델
```

---

## Backbone 개발 및 배포

### 개발 및 빌드 자세한 방법

```bash
# 1. 코드 수정
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/backbone/pod_sync/*.py

# 2. Docker 이미지 빌드 (필수!)
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/backbone/pod_sync

docker build -t <이미지 이름> .  # Ex) docker build -t ketidevit2/backbone:1.0 .

# 3. Docker 이미지 푸시 (필수!)
docker push <이미지 이름>  # Ex) docker push ketidevit2/backbone:1.0

# 4. Containerd에 Import (K3s에서 필수!)
#docker save ketidevit2/backbone:1.0 -o /tmp/backbone.tar

#sudo ctr -n k8s.io images import /tmp/backbone.tar

# 5. Kubernetes 배포/업데이트 (필수!)
# 배포 파일 수정: workloads/mission/yolo-backbone-move.yaml
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/yolo-backbone-move.yaml
# image: your-registry/backbone:latest 부분을 새 이미지로 변경

kubectl apply -f /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/yolo-backbone-move.yaml

# 또는 롤링 재시작
kubectl rollout restart deployment/yolov5-backbone

# 6. 확인
kubectl logs -l app=yolov5-backbone --tail=20
```

### 배포 파일 위치

- **배포 매니페스트**: `/root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/yolo-backbone-move.yaml`
- **Dockerfile**: `/root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/backbone/pod_sync/Dockerfile`

---

## Neck-Head-Slim 개발 및 배포

### 개발 및 빌드 자세한 방법

```bash
# 1. 코드 수정
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/neck-head-slim/app/*.py

# 2. Docker 이미지 빌드 (필수!)
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/neck-head-slim/app

docker build -t <이미지 이름> .  # Ex) docker build -t ketidevit2/neck-head-slim:1.0.3 .

# 3. Docker 이미지 푸시 (필수!)
docker push <이미지 이름>  # Ex) docker push ketidevit2/neck-head-slim:1.0.3

# 4. Containerd에 Import (K3s에서 필수!)
#docker save ketidevit2/neck-head-slim:1.0.3 -o /tmp/neck-head-slim.tar

#sudo ctr -n k8s.io images import /tmp/neck-head-slim.tar

# 5. Kubernetes 배포/업데이트 (필수!)
# 배포 파일 수정: workloads/mission/yolo-neck-head.yaml
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/yolo-neck-head.yaml
# image: ketidevit2/neck-head-slim:1.0.3 부분을 새 이미지로 변경

kubectl apply -f /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/yolo-neck-head.yaml

# 또는 롤링 재시작
kubectl rollout restart deployment/neck-head-deployment

# 6. 확인
kubectl logs -l app=neck-head --tail=20
kubectl get svc neck-head-service
```

### 배포 파일 위치

- **배포 매니페스트**: `/root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/yolo-neck-head.yaml`
- **Dockerfile**: `/root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/neck-head-slim/app/Dockerfile`

---

## Server 개발 및 배포

### 개발 및 빌드 자세한 방법

```bash
# 1. 코드 수정
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/server/pod_sync/*.py

# 2. Docker 이미지 빌드 (필수!)
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/server/pod_sync

docker build -t <이미지 이름> .  # Ex) docker build -t ketidevit2/yolo-image-server:1.0.0 .

# 3. Docker 이미지 푸시 (필수!)
docker push <이미지 이름>  # Ex) docker push ketidevit2/yolo-image-server:1.0.0

# 4. Containerd에 Import (K3s에서 필수!)
#docker save ketidevit2/yolo-image-server:1.0.0 -o /tmp/yolo-image-server.tar

#sudo ctr -n k8s.io images import /tmp/yolo-image-server.tar

# 5. Kubernetes 배포/업데이트 (필수!)
# 배포 파일 수정: workloads/mission/fastapi_image_server.yaml
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/fastapi_image_server.yaml
# image: ketidevit2/yolo-image-server:1.0.0 부분을 새 이미지로 변경

kubectl apply -f /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/fastapi_image_server.yaml

# 또는 롤링 재시작
kubectl rollout restart deployment/yolo-image-server

# 6. 확인
kubectl logs -l app=yolo-image-server --tail=20
kubectl get svc yolo-image-server-service
```

### 배포 파일 위치

- **배포 매니페스트**: `/root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/workloads/mission/fastapi_image_server.yaml`
- **Dockerfile**: `/root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/server/pod_sync/Dockerfile`

---

## YOLOv5 개발 및 배포

### 개발 및 빌드 자세한 방법

```bash
# 1. 코드 수정
vim /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/yolov5/yolov5/*.py

# 2. Docker 이미지 빌드 (필수!)
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/yolo/yolov5/yolov5

# Dockerfile이 있는 경우
docker build -t <이미지 이름> .  # Ex) docker build -t ketidevit2/yolov5:1.0 .

# 3. Docker 이미지 푸시 (필수!)
docker push <이미지 이름>  # Ex) docker push ketidevit2/yolov5:1.0

# 4. Containerd에 Import (K3s에서 필수!)
#docker save ketidevit2/yolov5:1.0 -o /tmp/yolov5.tar

#sudo ctr -n k8s.io images import /tmp/yolov5.tar

# 5. Kubernetes 배포/업데이트 (필수!)
# 배포 파일이 있는 경우 수정 후 적용
# kubectl apply -f <배포 파일 경로>

# 또는 롤링 재시작 (배포가 있는 경우)
# kubectl rollout restart deployment/<deployment-name>

# 6. 확인
# kubectl logs -l app=<app-label> --tail=20
```

**참고**: YOLOv5는 기본 모델 라이브러리로, 별도의 배포가 필요하지 않을 수 있습니다. 필요시 Backbone이나 Neck-Head-Slim에서 사용됩니다.

---

## 공통 사항

### 이미지 태그 규칙

- 버전 업데이트: `1.0` → `1.1` → `1.2`
- 개발 버전: `1.0-dev`, `1.0-test`
- 날짜 기반: `1.0-20241201`

### 배포 확인 명령어

```bash
# 모든 YOLO 관련 Pod 확인
kubectl get pods | grep -E "(backbone|neck-head|yolo-image-server)"

# 모든 YOLO 관련 Service 확인
kubectl get svc | grep -E "(backbone|neck-head|yolo-image-server)"

# 로그 확인
kubectl logs -l app=<app-label> -f
```

### 트러블슈팅

#### 이미지 Pull 실패

```bash
# 이미지를 로컬에 로드 (오프라인 환경)
docker load -i <image-name>.tar

# 또는 이미지 태그 수정 후 재배포
kubectl set image deployment/<deployment-name> <container-name>=<new-image> -n <namespace>
```

#### Pod가 시작되지 않음

```bash
# Pod 상태 확인
kubectl describe pod <pod-name>

# 이벤트 확인
kubectl get events --sort-by='.lastTimestamp' | grep <pod-name>
```

---

## 참고 자료

- [YOLOv5 공식 문서](https://github.com/ultralytics/yolov5)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Kubernetes 배포 가이드](../README.md)

