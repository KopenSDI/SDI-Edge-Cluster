#!/bin/bash

#############################################
# NotReady 노드 복구 스크립트
# turtlebot-burger-3 노드에서 실행하세요
#############################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================"
echo "NotReady 노드 복구 스크립트"
echo "======================================"
echo ""

# root 권한 확인
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}이 스크립트는 root 권한으로 실행해야 합니다.${NC}"
    echo "  sudo $0"
    exit 1
fi

# Control-plane IP 확인
read -p "Control-plane IP 주소를 입력하세요 (예: 10.0.0.39): " CONTROL_PLANE_IP
if [ -z "$CONTROL_PLANE_IP" ]; then
    echo -e "${RED}Control-plane IP가 입력되지 않았습니다.${NC}"
    exit 1
fi

# Control-plane과의 연결 확인
echo -e "${YELLOW}📡 Control-plane 연결 확인 중...${NC}"
if ! ping -c 2 "$CONTROL_PLANE_IP" &> /dev/null; then
    echo -e "${RED}❌ Control-plane($CONTROL_PLANE_IP)에 연결할 수 없습니다.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Control-plane 연결 확인${NC}"
echo ""

# k3s-agent 상태 확인
echo -e "${YELLOW}🔍 k3s-agent 상태 확인 중...${NC}"
if systemctl is-active --quiet k3s-agent; then
    echo -e "${BLUE}k3s-agent가 실행 중입니다. 재시작합니다...${NC}"
    systemctl restart k3s-agent
else
    echo -e "${YELLOW}k3s-agent가 실행되지 않았습니다. 시작합니다...${NC}"
    systemctl start k3s-agent
fi

# 잠시 대기
sleep 5

# 상태 재확인
if systemctl is-active --quiet k3s-agent; then
    echo -e "${GREEN}✓ k3s-agent 실행 중${NC}"
else
    echo -e "${RED}❌ k3s-agent 시작 실패${NC}"
    echo ""
    echo "로그 확인:"
    journalctl -u k3s-agent -n 30 --no-pager
    echo ""
    echo "토큰이 필요할 수 있습니다. Control-plane에서 다음 명령어로 토큰을 확인하세요:"
    echo "  sudo cat /var/lib/rancher/k3s/server/node-token"
    exit 1
fi

echo ""
echo -e "${YELLOW}📋 k3s-agent 로그 확인:${NC}"
journalctl -u k3s-agent -n 20 --no-pager | tail -10

echo ""
echo "======================================"
echo -e "${GREEN}복구 완료! 🎉${NC}"
echo "======================================"
echo ""
echo "Control-plane에서 다음 명령어로 노드 상태를 확인하세요:"
echo "  kubectl get nodes"
echo "  kubectl get nodes -w  # 실시간 모니터링"
echo ""

