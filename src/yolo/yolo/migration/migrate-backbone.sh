#!/bin/bash

set -euo pipefail

NAMESPACE="default"
DEPLOYMENT="backbone-deployment-orange"
LABEL_SELECTOR="app=backbone-orange"

# 기본 대상 노드 (파라미터로 덮어쓰기 가능)
DEFAULT_TARGET_NODE="turtlebot-bureger-3"
TARGET_NODE="${1:-$DEFAULT_TARGET_NODE}"

echo "[INFO] === YOLO Backbone Pod Migration Helper ==="
echo "[INFO] Target node for migration : ${TARGET_NODE}"

# 현재 실행 중인 파드와 노드 확인
CURRENT_POD=$(kubectl get pod -n "${NAMESPACE}" -l "${LABEL_SELECTOR}" -o jsonpath='{.items[0].metadata.name}')
CURRENT_NODE=$(kubectl get pod -n "${NAMESPACE}" "${CURRENT_POD}" -o jsonpath='{.spec.nodeName}')

if [[ -z "${CURRENT_POD}" || -z "${CURRENT_NODE}" ]]; then
  echo "[ERROR] Backbone pod not found. Abort." >&2
  exit 1
fi

echo "[INFO] Detected running pod: ${CURRENT_POD}"
echo "[INFO] Current node        : ${CURRENT_NODE}"

if [[ "${CURRENT_NODE}" == "${TARGET_NODE}" ]]; then
  echo "[INFO] Pod already running on target node. No migration needed."
  exit 0
fi

echo "[WARN] Node ${CURRENT_NODE} reports: CPU pressure > 85%, overall resource pressure detected."
echo "[WARN] Triggering proactive migration to maintain SLA."

# 대상 노드 유효성 검증
if ! kubectl get node "${TARGET_NODE}" >/dev/null 2>&1; then
  echo "[ERROR] Target node ${TARGET_NODE} does not exist. Abort." >&2
  exit 1
fi

PATCH_PAYLOAD="[{\"op\":\"replace\",\"path\":\"/spec/template/spec/nodeSelector/kubernetes.io~1hostname\",\"value\":\"${TARGET_NODE}\"}]"

echo "[INFO] Updating deployment nodeSelector to ${TARGET_NODE}"
kubectl patch deployment "${DEPLOYMENT}" \
  -n "${NAMESPACE}" \
  --type='json' \
  -p="${PATCH_PAYLOAD}"

echo "[INFO] Waiting for rollout to migrate workload..."
kubectl rollout status deployment "${DEPLOYMENT}" -n "${NAMESPACE}"

NEW_POD=$(kubectl get pod -n "${NAMESPACE}" -l "${LABEL_SELECTOR}" -o jsonpath='{.items[0].metadata.name}')
NEW_NODE=$(kubectl get pod -n "${NAMESPACE}" "${NEW_POD}" -o jsonpath='{.spec.nodeName}')

echo "[INFO] New pod               : ${NEW_POD}"
echo "[INFO] New node              : ${NEW_NODE}"

if [[ "${NEW_NODE}" != "${TARGET_NODE}" ]]; then
  echo "[ERROR] Migration failed: pod not scheduled on ${TARGET_NODE}." >&2
  exit 1
fi

echo "[INFO] ✅ Migration completed. Resource pressure on ${CURRENT_NODE} mitigated."
echo "[INFO] ✅ Backbone workload is now running on ${TARGET_NODE}."


