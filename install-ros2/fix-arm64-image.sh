#!/bin/bash

#############################################
# ARM64 노드에서 잘못된 아키텍처 이미지 삭제 및 재pull
# turtlebot-burger-1 노드에서 실행
#############################################

echo "ARM64 노드에서 ros-humble 이미지 정리 중..."

# K3s에서 이미지 삭제
k3s ctr images rm docker.io/ketidevit2/ros-humble:1.0.2 2>/dev/null || true

# 또는 containerd 직접 사용
crictl rmi docker.io/ketidevit2/ros-humble:1.0.2 2>/dev/null || true

echo "이미지 삭제 완료. 이제 파드를 다시 생성하면 올바른 ARM64 이미지를 pull합니다."

