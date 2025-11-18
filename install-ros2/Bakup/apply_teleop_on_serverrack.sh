#!/bin/bash
set -euo pipefail

YAML_FILE="teleop-on-serverrack.yaml"
NAMESPACE="ros"
DEPLOY_NAME="teleop-on-serverrack"

# 네임스페이스 보장
kubectl create ns "${NAMESPACE}" >/dev/null 2>&1 || true

# CycloneDDS ConfigMap 존재 확인 (없으면 안내)
if ! kubectl -n "${NAMESPACE}" get configmap cyclonedds-config >/dev/null 2>&1; then
  echo "⚠️  'cyclonedds-config' ConfigMap이 ${NAMESPACE} 네임스페이스에 없습니다."
  echo "   먼저 CycloneDDS ConfigMap을 생성하세요. (ex: setup_cyclonedds_config.sh)"
  exit 1
fi

# YAML 적용
kubectl apply -f "${YAML_FILE}"

# 롤아웃 확인
kubectl -n "${NAMESPACE}" rollout status deploy/"${DEPLOY_NAME}" --timeout=120s

# 파드 이름 출력
POD=$(kubectl -n "${NAMESPACE}" get pod -l app=teleop-svr -o jsonpath='{.items[0].metadata.name}')
echo "✅ 배포 완료: ${DEPLOY_NAME}"
echo "🔎 Pod: ${POD}"
echo
echo "teleop 실행 예:"
echo "  kubectl -n ${NAMESPACE} exec -it ${POD} -- bash -lc 'source /opt/ros/humble/setup.bash && ros2 run teleop_twist_keyboard teleop_twist_keyboard'"

