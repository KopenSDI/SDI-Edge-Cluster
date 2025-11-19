#!/bin/bash

#############################################
# YOLO YAML 파일 일괄 배포 스크립트
# yolo_yaml 디렉토리의 모든 yaml 파일을 kubectl apply로 실행합니다
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

echo "======================================"
echo "YOLO YAML 파일 일괄 배포"
echo "======================================"
echo ""

# kubectl 명령어 확인
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl 명령어를 찾을 수 없습니다.${NC}"
    echo "K3s가 설치되어 있고 kubectl이 PATH에 있는지 확인하세요."
    exit 1
fi

# kubeconfig 확인
if [ ! -f "/etc/rancher/k3s/k3s.yaml" ] && [ -z "$KUBECONFIG" ]; then
    echo -e "${YELLOW}⚠ KUBECONFIG가 설정되지 않았습니다.${NC}"
    echo "다음 명령어로 설정하세요:"
    echo "  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
    echo ""
    read -p "계속 진행하시겠습니까? (y/n): " continue_choice
    if [ "$continue_choice" != "y" ] && [ "$continue_choice" != "Y" ]; then
        exit 0
    fi
fi

# yaml 파일 찾기
echo -e "${BLUE}📋 YAML 파일 검색 중...${NC}"
YAML_FILES=$(find "$SCRIPT_DIR" -type f \( -name "*.yaml" -o -name "*.yml" \) | grep -v "apply-all-yaml.sh" | sort)

if [ -z "$YAML_FILES" ]; then
    echo -e "${RED}❌ YAML 파일을 찾을 수 없습니다.${NC}"
    exit 1
fi

# 찾은 파일 목록 표시
echo -e "${GREEN}✓ 발견된 YAML 파일:${NC}"
echo "$YAML_FILES" | while read -r file; do
    echo "  - $(basename $(dirname $file))/$(basename $file)"
done
echo ""

# 배포 확인
read -p "위 파일들을 모두 배포하시겠습니까? (y/n): " deploy_choice
if [ "$deploy_choice" != "y" ] && [ "$deploy_choice" != "Y" ]; then
    echo "배포가 취소되었습니다."
    exit 0
fi

echo ""
echo -e "${YELLOW}🚀 배포 시작...${NC}"
echo ""

# 각 파일 배포
SUCCESS_COUNT=0
FAIL_COUNT=0
FAILED_FILES=()

while IFS= read -r yaml_file; do
    if [ -f "$yaml_file" ]; then
        file_name=$(basename "$yaml_file")
        dir_name=$(basename $(dirname "$yaml_file"))
        echo -e "${BLUE}📦 배포 중: $dir_name/$file_name${NC}"
        
        if kubectl apply -f "$yaml_file"; then
            echo -e "${GREEN}✓ 성공: $file_name${NC}"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo -e "${RED}❌ 실패: $file_name${NC}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            FAILED_FILES+=("$yaml_file")
        fi
        echo ""
    fi
done <<< "$YAML_FILES"

# 결과 요약
echo "======================================"
echo -e "${GREEN}배포 완료! 🎉${NC}"
echo "======================================"
echo ""
echo -e "${BLUE}📊 배포 결과:${NC}"
echo "  성공: $SUCCESS_COUNT개"
echo "  실패: $FAIL_COUNT개"
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${RED}❌ 실패한 파일:${NC}"
    for file in "${FAILED_FILES[@]}"; do
        echo "  - $file"
    done
    echo ""
fi

# 배포된 리소스 확인
echo -e "${BLUE}📋 배포된 리소스 확인:${NC}"
echo ""
echo "Deployments:"
kubectl get deployments -A | grep -E "(yolo|NAME)" || echo "  (yolo 관련 Deployment 없음)"
echo ""
echo "Services:"
kubectl get services -A | grep -E "(yolo|NAME)" || echo "  (yolo 관련 Service 없음)"
echo ""
echo "Pods:"
kubectl get pods -A | grep -E "(yolo|NAME)" || echo "  (yolo 관련 Pod 없음)"
echo ""

echo -e "${BLUE}💡 유용한 명령어:${NC}"
echo "  kubectl get pods -A | grep yolo"
echo "  kubectl logs -f <pod-name> -n <namespace>"
echo "  kubectl describe pod <pod-name> -n <namespace>"
echo ""

