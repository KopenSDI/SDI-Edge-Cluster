#!/bin/bash

#############################################
# K3s 오프라인 설치 파일 다운로드 스크립트
# 필요한 k3s 바이너리와 이미지 파일을 다운로드합니다
#############################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 변수 설정
K3S_VERSION=${K3S_VERSION:-"v1.33.4+k3s1"}
ARCH=${ARCH:-"amd64"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOAD_DIR="$SCRIPT_DIR"

echo "======================================"
echo "K3s 오프라인 설치 파일 다운로드"
echo "======================================"
echo ""
echo "K3s 버전: $K3S_VERSION"
echo "아키텍처: $ARCH"
echo "다운로드 위치: $DOWNLOAD_DIR"
echo ""

# 다운로드 디렉토리로 이동
cd "$DOWNLOAD_DIR"

# K3S 버전에서 + 제거 (URL용)
URL_VERSION=$(echo $K3S_VERSION | sed 's/+/%2B/g')

# 1. K3s 바이너리 다운로드
echo -e "${YELLOW}📥 K3s 바이너리 다운로드 중...${NC}"
if [ ! -f "k3s" ]; then
    echo "  URL: https://github.com/k3s-io/k3s/releases/download/${URL_VERSION}/k3s"
    wget -q --show-progress "https://github.com/k3s-io/k3s/releases/download/${URL_VERSION}/k3s" || {
        echo -e "${RED}K3s 바이너리 다운로드 실패${NC}"
        exit 1
    }
    chmod +x k3s
    echo -e "${GREEN}✓ K3s 바이너리 다운로드 완료${NC}"
else
    echo -e "${GREEN}✓ K3s 바이너리 이미 존재합니다${NC}"
fi
echo ""

# 2. Air-gap 이미지 다운로드
echo -e "${YELLOW}📥 Air-gap 이미지 다운로드 중 (약 500MB)...${NC}"
IMAGE_FILE="k3s-airgap-images-${ARCH}.tar.gz"
if [ ! -f "$IMAGE_FILE" ]; then
    echo "  URL: https://github.com/k3s-io/k3s/releases/download/${URL_VERSION}/k3s-airgap-images-${ARCH}.tar.gz"
    wget -q --show-progress "https://github.com/k3s-io/k3s/releases/download/${URL_VERSION}/k3s-airgap-images-${ARCH}.tar.gz" || {
        echo -e "${RED}Air-gap 이미지 다운로드 실패${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Air-gap 이미지 다운로드 완료${NC}"
else
    echo -e "${GREEN}✓ Air-gap 이미지 이미 존재합니다${NC}"
fi
echo ""

# 다운로드된 파일 확인
echo "======================================"
echo -e "${GREEN}다운로드 완료! 🎉${NC}"
echo "======================================"
echo ""
echo -e "${BLUE}다운로드된 파일:${NC}"
ls -lh k3s k3s-airgap-images-${ARCH}.tar.gz 2>/dev/null || ls -lh "$DOWNLOAD_DIR" | grep -E "(k3s|k3s-airgap)"
echo ""
echo -e "${BLUE}다음 단계:${NC}"
echo "  sudo ./00.k3s_offline_install.sh 를 실행하고 모드 2를 선택하세요"
echo "  (파일이 같은 디렉토리에 있으므로 자동으로 인식됩니다)"
echo ""


