#!/bin/bash

#############################################
# TurtleBot PC ROS 2 Discovery Server 설정
# Kubernetes Pod와 통신하기 위한 설정
#############################################

echo "======================================"
echo "TurtleBot PC ROS 2 Discovery 설정"
echo "======================================"

# Control Plane IP 설정 (실제 IP로 변경 필요)
CONTROL_PLANE_IP="10.0.0.39"
DISCOVERY_PORT="11811"

echo "Control Plane IP: $CONTROL_PLANE_IP"
echo "Discovery Port: $DISCOVERY_PORT"
echo ""

# 환경 변수 설정
echo "ROS 2 환경 변수 설정 중..."

# ROS 2 미들웨어 설정
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# Discovery Server 설정
export ROS_DISCOVERY_SERVER="$CONTROL_PLANE_IP:$DISCOVERY_PORT"

# ROS Domain ID 설정 (Kubernetes와 동일하게)
export ROS_DOMAIN_ID=30

# TurtleBot3 모델 설정
export TURTLEBOT3_MODEL=burger

echo "✅ 환경 변수 설정 완료:"
echo "  RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION"
echo "  ROS_DISCOVERY_SERVER: $ROS_DISCOVERY_SERVER"
echo "  ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "  TURTLEBOT3_MODEL: $TURTLEBOT3_MODEL"
echo ""

# ROS 2 환경 소스
echo "ROS 2 환경 소스 중..."
source /opt/ros/humble/setup.bash

# TurtleBot3 워크스페이스 소스 (있는 경우)
if [ -f "/home/ubuntu/turtlebot3_ws/install/setup.bash" ]; then
    echo "TurtleBot3 워크스페이스 소스 중..."
    source /home/ubuntu/turtlebot3_ws/install/setup.bash
fi

echo "✅ ROS 2 환경 설정 완료"
echo ""

# Discovery Server 연결 테스트
echo "Discovery Server 연결 테스트 중..."
echo "ping -c 3 $CONTROL_PLANE_IP"

if ping -c 3 $CONTROL_PLANE_IP > /dev/null 2>&1; then
    echo "✅ Control Plane 연결 성공"
else
    echo "❌ Control Plane 연결 실패"
    echo "IP 주소를 확인해주세요: $CONTROL_PLANE_IP"
fi

echo ""
echo "======================================"
echo "설정 완료!"
echo "======================================"
echo ""
echo "이제 다음 명령어로 ROS 2 노드를 실행할 수 있습니다:"
echo ""
echo "# TurtleBot3 원격 조종"
echo "ros2 run turtlebot3_teleop teleop_keyboard"
echo ""
echo "# TurtleBot3 상태 확인"
echo "ros2 topic list"
echo "ros2 node list"
echo ""
echo "주의: 이 설정은 현재 터미널 세션에서만 유효합니다."
echo "영구적으로 설정하려면 ~/.bashrc에 추가하세요."
