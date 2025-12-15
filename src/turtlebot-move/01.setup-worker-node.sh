#!/bin/bash

# 워커 노드에 경로를 만들고 smooth_move.sh 스크립트를 복사하는 스크립트
# 사용법: ./setup-worker-node.sh <USER@HOST>
# 예시: ./setup-worker-node.sh root@10.0.0.201

# 인자 확인
if [ $# -lt 1 ]; then
    echo "사용법: $0 <USER@HOST>"
    echo "예시: $0 root@10.0.0.201"
    exit 1
fi

# USER@HOST 형식 파싱
USER_HOST=$1

# 비밀번호 입력 받기
echo -n "Enter password: "
read -s PASSWORD
echo ""

# @ 기호로 분리
if [[ "$USER_HOST" == *"@"* ]]; then
    USER=$(echo $USER_HOST | cut -d'@' -f1)
    HOST=$(echo $USER_HOST | cut -d'@' -f2)
else
    echo "오류: USER@HOST 형식이 아닙니다. 예: root@10.0.0.201"
    exit 1
fi

WORKER_IP=$HOST
WORKER_USER=$USER
SCRIPT_DIR="/root/KETI_SDI_Edge_Cluster/SDI_Edge_Cluster/src/turtlebot-move"
SCRIPT_FILE="smooth_move.sh"

# 현재 스크립트의 디렉토리 경로 확인
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SCRIPT="${CURRENT_DIR}/${SCRIPT_FILE}"

# 소스 스크립트 파일 존재 확인
if [ ! -f "$SOURCE_SCRIPT" ]; then
    echo "오류: $SOURCE_SCRIPT 파일을 찾을 수 없습니다."
    exit 1
fi

echo "========================================="
echo "워커 노드 설정 시작: $WORKER_USER@$WORKER_IP"
echo "========================================="

# sshpass 설치 확인
if ! command -v sshpass &> /dev/null; then
    echo "sshpass가 설치되어 있지 않습니다. 설치 중..."
    apt-get update && apt-get install -y sshpass
fi

# 1. 디렉토리 생성 (이미 존재해도 에러 없음)
echo "[1/3] 워커 노드에 디렉토리 생성 중..."
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $WORKER_USER@$WORKER_IP "mkdir -p $SCRIPT_DIR 2>/dev/null; echo '디렉토리 확인 완료'" 2>&1 | grep -v "Warning: Permanently added" | grep -v "^$"
if [ $? -eq 0 ]; then
    echo "✓ 디렉토리 확인 완료: $SCRIPT_DIR"
else
    echo "✗ 디렉토리 생성/확인 실패"
    exit 1
fi

# 2. 스크립트 파일 복사
echo "[2/3] 스크립트 파일 복사 중..."
SCP_OUTPUT=$(sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no "$SOURCE_SCRIPT" $WORKER_USER@$WORKER_IP:$SCRIPT_DIR/ 2>&1)
SCP_EXIT_CODE=$?
# 경고 메시지만 필터링하고 에러는 표시
echo "$SCP_OUTPUT" | grep -v "Warning: Permanently added" | grep -v "^$" || true
if [ $SCP_EXIT_CODE -eq 0 ]; then
    echo "✓ 스크립트 파일 복사 완료: $SCRIPT_FILE"
else
    echo "✗ 스크립트 파일 복사 실패 (exit code: $SCP_EXIT_CODE)"
    echo "에러 상세: $SCP_OUTPUT"
    exit 1
fi

# 3. 실행 권한 부여 및 확인
echo "[3/3] 실행 권한 부여 및 확인 중..."
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $WORKER_USER@$WORKER_IP "chmod +x $SCRIPT_DIR/$SCRIPT_FILE && ls -la $SCRIPT_DIR/$SCRIPT_FILE" 2>&1 | grep -v "Warning: Permanently added" | grep -v "^$"
if [ $? -eq 0 ]; then
    echo "✓ 실행 권한 부여 완료"
else
    echo "✗ 실행 권한 부여 실패"
    exit 1
fi

echo "========================================="
echo "워커 노드 설정 완료: $WORKER_USER@$WORKER_IP"
echo "========================================="
echo ""
echo "확인:"
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $WORKER_USER@$WORKER_IP "ls -la $SCRIPT_DIR/" 2>&1 | grep -v "Warning: Permanently added" | grep -v "^$"

