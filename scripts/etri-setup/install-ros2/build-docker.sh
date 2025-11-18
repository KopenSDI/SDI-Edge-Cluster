#!/bin/bash

#############################################
# ROS2 Docker 이미지 멀티 아키텍처 빌드 스크립트
# AMD64 및 ARM64 아키텍처 지원
#############################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 기본값 설정
IMAGE_NAME="${IMAGE_NAME:-ketidevit2/ros-humble}"
IMAGE_TAG="${IMAGE_TAG:-1.0.2}"
BUILD_ARCH="${BUILD_ARCH:-amd64,arm64}"  # 기본값: 둘 다 빌드

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ROS2 Docker 이미지 멀티 아키텍처 빌드${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}이미지명: ${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo -e "${YELLOW}빌드 아키텍처: ${BUILD_ARCH}${NC}"
echo ""

# Docker Buildx 확인 및 설정
if ! docker buildx version &> /dev/null; then
    echo -e "${RED}❌ Docker Buildx가 설치되어 있지 않습니다.${NC}"
    echo "Docker Buildx를 설치하거나 Docker Desktop을 업데이트하세요."
    exit 1
fi

# Buildx builder 생성 (없는 경우) 또는 재생성
BUILDER_NAME="multiarch-builder"
if docker buildx ls | grep -q "$BUILDER_NAME"; then
    echo -e "${YELLOW}📦 기존 Buildx builder 삭제 중...${NC}"
    docker buildx rm "$BUILDER_NAME" 2>/dev/null || true
fi

echo -e "${YELLOW}📦 Buildx builder 생성 중...${NC}"
docker buildx create --name "$BUILDER_NAME" --driver docker-container --use --bootstrap
echo -e "${GREEN}  ✓ Buildx builder 생성 완료${NC}"

# QEMU 설정 (멀티 아키텍처 에뮬레이션)
echo -e "${YELLOW}🔧 QEMU 설정 중...${NC}"
echo -e "${YELLOW}  QEMU binfmt 재설치 중...${NC}"
docker run --rm --privileged tonistiigi/binfmt --install all
echo -e "${GREEN}  ✓ QEMU 설치 완료${NC}"

# 빌드 모드 선택
if [[ "$BUILD_ARCH" == *","* ]]; then
    # 멀티 아키텍처 빌드 (push 모드)
    echo -e "${BLUE}🚀 멀티 아키텍처 빌드 시작 (${BUILD_ARCH})...${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  주의: 멀티 아키텍처 빌드는 Docker Hub에 push해야 합니다.${NC}"
    echo -e "${YELLOW}    또는 --load 옵션을 사용하여 로컬에 저장하세요.${NC}"
    echo ""
    
    read -p "Docker Hub에 push하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}📤 Docker Hub에 push 중...${NC}"
        docker buildx build \
            --platform linux/amd64,linux/arm64 \
            --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
            --tag "${IMAGE_NAME}:latest" \
            --push \
            .
    else
        echo -e "${YELLOW}💾 로컬에 저장 중 (amd64만)...${NC}"
        docker buildx build \
            --platform linux/amd64 \
            --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
            --tag "${IMAGE_NAME}:latest" \
            --load \
            .
        echo -e "${YELLOW}⚠️  ARM64 빌드는 로컬 저장이 불가능합니다.${NC}"
        echo -e "${YELLOW}    ARM64 빌드는 Docker Hub push 모드로만 가능합니다.${NC}"
    fi
else
    # 단일 아키텍처 빌드
    echo -e "${BLUE}🚀 단일 아키텍처 빌드 시작 (${BUILD_ARCH})...${NC}"
    
    if [[ "$BUILD_ARCH" == "amd64" ]]; then
        PLATFORM="linux/amd64"
    elif [[ "$BUILD_ARCH" == "arm64" ]]; then
        PLATFORM="linux/arm64"
    else
        echo -e "${RED}❌ 지원하지 않는 아키텍처: ${BUILD_ARCH}${NC}"
        echo "지원되는 아키텍처: amd64, arm64"
        exit 1
    fi
    
    docker buildx build \
        --platform "$PLATFORM" \
        --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
        --tag "${IMAGE_NAME}:latest" \
        --load \
        .
fi

echo ""
echo -e "${GREEN}✅ 빌드 완료!${NC}"
echo ""
echo -e "${BLUE}📋 사용법:${NC}"
echo "  # 단일 아키텍처 빌드 (AMD64)"
echo "  BUILD_ARCH=amd64 ./build-docker.sh"
echo ""
echo "  # 단일 아키텍처 빌드 (ARM64)"
echo "  BUILD_ARCH=arm64 ./build-docker.sh"
echo ""
echo "  # 멀티 아키텍처 빌드 (AMD64 + ARM64)"
echo "  BUILD_ARCH=amd64,arm64 ./build-docker.sh"
echo ""
echo "  # 이미지명 및 태그 지정"
echo "  IMAGE_NAME=ketidevit2/ros-humble IMAGE_TAG=1.0.3 ./build-docker.sh"

