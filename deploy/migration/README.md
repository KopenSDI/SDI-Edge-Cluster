# SDI Migration Service

MALE 기반 정책 엔진 및 클러스터 가용 자원 기반 마이그레이션 서비스입니다.

## 개요

SDI Migration Service는 다음 기능을 제공합니다:

1. **자동 리소스 모니터링**: 클러스터의 노드 및 Pod 리소스 사용량을 주기적으로 모니터링
2. **정책 기반 마이그레이션**: MALE 정책 엔진과 연동하여 마이그레이션 결정
3. **체크포인팅 지원**: Pod 상태를 체크포인트하여 무중단 마이그레이션 지원
4. **지능형 노드 선택**: 리소스 여유도 기반으로 최적의 대상 노드 자동 선택

## 주요 기능

### 1. 리소스 압박도 기반 마이그레이션
- CPU 및 Memory 사용률이 임계값(기본 85%)을 초과하는 노드 감지
- 해당 노드의 Pod들을 자동으로 마이그레이션

### 2. 정책 엔진 연동
- Policy Engine과 연동하여 마이그레이션 허용 여부 확인
- 혼합 중요도(Mixed Criticality) 기반 마이그레이션 정책 적용

### 3. 체크포인팅/상태 전송
- Pod의 상태를 체크포인트로 저장
- 마이그레이션 후 상태 복원 지원

### 4. Deployment 기반 마이그레이션
- Deployment의 nodeSelector를 업데이트하여 롤링 업데이트 방식으로 마이그레이션
- 단일 Pod의 경우 Eviction API를 사용하여 재스케줄링

## 배포 방법

### 1. InfluxDB 토큰 설정

`SDI-Migration-deploy.yaml` 파일의 43번째 줄에 InfluxDB 토큰을 입력합니다:

```yaml
stringData:
  token: <디비 토큰 값 입력 - README 참고> # 직접 작성
```

### 2. 배포 실행

```bash
cd /root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/deploy/migration
kubectl apply -f SDI-Migration-deploy.yaml
```

### 3. 상태 확인

```bash
kubectl get pod -n kube-system | grep sdi-migration
kubectl logs -f -n kube-system -l app=sdi-migration
```

## 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `INFLUX_URL` | InfluxDB URL | `http://influxdb.tbot-monitoring.svc.cluster.local:8086` |
| `INFLUX_ORG` | InfluxDB Organization | `keti` |
| `INFLUX_BUCKET` | InfluxDB Bucket | `turtlebot` |
| `INFLUX_TOKEN` | InfluxDB Token | (Secret에서 주입) |
| `POLICY_ENGINE_URL` | Policy Engine URL | `http://policy-engine.orchestration-engines.svc.cluster.local:8080` |
| `ANALYSIS_ENGINE_URL` | Analysis Engine URL | `http://analysis-engine.orchestration-engines.svc.cluster.local:8080` |
| `MIGRATION_CHECK_INTERVAL` | 모니터링 주기 (초) | `30` |
| `RESOURCE_PRESSURE_THRESHOLD` | 리소스 압박 임계값 (%) | `85` |
| `ENABLE_CHECKPOINTING` | 체크포인팅 활성화 여부 | `true` |

## 동작 방식

1. **모니터링 루프**: 설정된 주기(기본 30초)마다 모든 노드의 리소스 사용량 확인
2. **압박도 감지**: CPU 또는 Memory 사용률이 임계값을 초과하는 노드 감지
3. **대상 Pod 선택**: 해당 노드에서 실행 중인 Pod 중 마이그레이션 대상 선택
4. **정책 확인**: Policy Engine에 마이그레이션 허용 여부 확인
5. **대상 노드 선택**: 리소스 여유도가 가장 높은 노드 자동 선택
6. **체크포인트 생성**: Pod 상태를 체크포인트로 저장 (활성화된 경우)
7. **마이그레이션 수행**: Deployment 업데이트 또는 Pod Eviction을 통한 마이그레이션
8. **상태 복원**: 체크포인트에서 상태 복원 (활성화된 경우)
9. **메트릭 기록**: 마이그레이션 결과를 InfluxDB에 기록

## API 엔드포인트 (정책 엔진)

Migration Service는 Policy Engine의 다음 API를 호출합니다:

```
POST /api/v1/migration/policy
Content-Type: application/json

{
  "pod": {
    "name": "pod-name",
    "namespace": "default",
    "node_name": "source-node",
    "labels": {...}
  },
  "source_node": "source-node",
  "target_node": "target-node"
}

Response:
{
  "allowed": true,
  "reason": "Migration allowed by policy"
}
```

## 체크포인팅

체크포인팅 기능은 `ENABLE_CHECKPOINTING` 환경 변수로 제어됩니다.

현재 구현은 시뮬레이션 단계이며, 실제 체크포인팅을 위해서는:
- CRI-O 또는 containerd의 checkpoint 기능 활용
- `kubectl checkpoint` 명령어 또는 CRI API 사용
- 체크포인트 데이터 저장소 구성

## 메트릭

마이그레이션 메트릭은 InfluxDB에 다음과 같은 형식으로 기록됩니다:

```
Measurement: pod_migration
Tags:
  - pod_name: 마이그레이션된 Pod 이름
  - source_node: 원본 노드
  - target_node: 대상 노드
  - success: 성공 여부 (true/false)
Fields:
  - migration_count: 1
```

## 트러블슈팅

### 마이그레이션이 수행되지 않는 경우

1. 로그 확인:
   ```bash
   kubectl logs -n kube-system -l app=sdi-migration
   ```

2. RBAC 권한 확인:
   ```bash
   kubectl get clusterrole sdi-migration
   kubectl get clusterrolebinding sdi-migration
   ```

3. Policy Engine 연결 확인:
   ```bash
   kubectl exec -n kube-system -l app=sdi-migration -- curl http://policy-engine.orchestration-engines.svc.cluster.local:8080/health
   ```

### 리소스 임계값 조정

`SDI-Migration-deploy.yaml`의 ConfigMap에서 `RESOURCE_PRESSURE_THRESHOLD` 값을 수정:

```yaml
data:
  RESOURCE_PRESSURE_THRESHOLD: "75"  # 75%로 변경
```

## 참고 자료

- [Kubernetes Eviction API](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-eviction/)
- [Kubernetes Deployment Rolling Update](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment)
- [CRI Checkpoint/Restore](https://github.com/checkpoint-restore/criu)

