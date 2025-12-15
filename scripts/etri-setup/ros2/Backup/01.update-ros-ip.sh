#!/bin/bash

#############################################
# ROS2 YAML 파일 IP 주소 수정 스크립트
# ros-pod-Domain-31.yaml과 ros-pod-Domain-32.yaml의 IP 주소를 변경합니다
#############################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 스크립트 디렉토리 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_POD_31_YAML="$SCRIPT_DIR/ros-pod-Domain-31.yaml"
ROS_POD_32_YAML="$SCRIPT_DIR/ros-pod-Domain-32.yaml"

echo "======================================"
echo "ROS2 YAML 파일 IP 주소 수정"
echo "======================================"
echo ""

# 파일 존재 확인
if [ ! -f "$ROS_POD_31_YAML" ]; then
    echo -e "${RED}❌ ros-pod-Domain-31.yaml 파일을 찾을 수 없습니다: $ROS_POD_31_YAML${NC}"
    exit 1
fi

if [ ! -f "$ROS_POD_32_YAML" ]; then
    echo -e "${RED}❌ ros-pod-Domain-32.yaml 파일을 찾을 수 없습니다: $ROS_POD_32_YAML${NC}"
    exit 1
fi

# IP 주소 입력 또는 자동 감지
if [ -n "$1" ]; then
    NEW_IP="$1"
    echo -e "${BLUE}사용자 지정 IP: $NEW_IP${NC}"
else
    # 현재 서버의 IP 주소 자동 감지
    echo -e "${YELLOW}IP 주소 자동 감지 중...${NC}"
    
    # 기본 라우트의 인터페이스 IP 찾기
    NEW_IP=$(ip route get 8.8.8.8 2>/dev/null | grep -oP 'src \K\S+' | head -1)
    
    if [ -z "$NEW_IP" ]; then
        # 대체 방법: 활성 이더넷 인터페이스의 IP 찾기
        NEW_IP=$(ip addr show | grep -E "inet.*eth|inet.*ens|inet.*enp" | grep -v "127.0.0.1" | head -1 | awk '{print $2}' | cut -d'/' -f1)
    fi
    
    if [ -z "$NEW_IP" ]; then
        echo -e "${RED}❌ IP 주소를 자동으로 감지할 수 없습니다.${NC}"
        echo ""
        read -p "IP 주소를 입력하세요 (예: 10.0.0.39): " NEW_IP
        if [ -z "$NEW_IP" ]; then
            echo -e "${RED}IP 주소가 입력되지 않았습니다.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ 감지된 IP: $NEW_IP${NC}"
    fi
fi

# IP 주소 형식 검증
if ! [[ $NEW_IP =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    echo -e "${RED}❌ 잘못된 IP 주소 형식입니다: $NEW_IP${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}현재 설정 확인:${NC}"

# 기존 IP 주소 확인
OLD_IP=$(grep -E "ROS_DISCOVERY_SERVER|value.*10\.0\.0\." "$ROS_POD_31_YAML" "$ROS_POD_32_YAML" 2>/dev/null | grep -oP '10\.\d+\.\d+\.\d+' | head -1 || echo "찾을 수 없음")
if [ "$OLD_IP" != "찾을 수 없음" ]; then
    echo "  기존 IP: $OLD_IP"
else
    echo "  기존 IP: (찾을 수 없음)"
fi

echo "  새 IP: $NEW_IP"
echo ""

# 확인
read -p "위 IP 주소로 변경하시겠습니까? (y/n): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "취소되었습니다."
    exit 0
fi

# IP 주소 변경
echo -e "${YELLOW}🔄 IP 주소 변경 중...${NC}"

# ros-pod-Domain-31.yaml의 ROS_DISCOVERY_SERVER 값 변경
if grep -q "ROS_DISCOVERY_SERVER" "$ROS_POD_31_YAML"; then
    # sed를 사용하여 IP 주소 변경 (10.0.0.39 형식의 IP를 찾아서 변경)
    sed -i "s|value: \"10\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}:11811\"|value: \"$NEW_IP:11811\"|g" "$ROS_POD_31_YAML"
    sed -i "s|value: \"[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}:11811\"|value: \"$NEW_IP:11811\"|g" "$ROS_POD_31_YAML"
    echo -e "${GREEN}✓ ros-pod-Domain-31.yaml 업데이트 완료${NC}"
else
    echo -e "${YELLOW}⚠ ros-pod-Domain-31.yaml에서 ROS_DISCOVERY_SERVER를 찾을 수 없습니다.${NC}"
fi

# ros-pod-Domain-32.yaml의 ROS_DISCOVERY_SERVER 값 변경
if grep -q "ROS_DISCOVERY_SERVER" "$ROS_POD_32_YAML"; then
    # sed를 사용하여 IP 주소 변경 (10.0.0.39 형식의 IP를 찾아서 변경)
    sed -i "s|value: \"10\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}:11811\"|value: \"$NEW_IP:11811\"|g" "$ROS_POD_32_YAML"
    sed -i "s|value: \"[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}:11811\"|value: \"$NEW_IP:11811\"|g" "$ROS_POD_32_YAML"
    echo -e "${GREEN}✓ ros-pod-Domain-32.yaml 업데이트 완료${NC}"
else
    echo -e "${YELLOW}⚠ ros-pod-Domain-32.yaml에서 ROS_DISCOVERY_SERVER를 찾을 수 없습니다.${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}변경 완료! 🎉${NC}"
echo "======================================"
echo ""
echo -e "${BLUE}변경된 내용:${NC}"
echo "  파일: ros-pod-Domain-31.yaml"
echo "  환경 변수: ROS_DISCOVERY_SERVER"
echo "  값: $NEW_IP:11811"
echo "  파일: ros-pod-Domain-32.yaml"
echo "  환경 변수: ROS_DISCOVERY_SERVER"
echo "  값: $NEW_IP:11811"
echo ""
echo -e "${BLUE}다음 단계:${NC}"
echo "  ./01.setup-turtlebot-pod.sh 를 실행하여 변경된 설정으로 배포하세요"
echo ""

