#!/bin/bash
# KETI SDI-Orchestration 오프라인 환경 설정 스크립트 (Part 1)

set -e

echo "✅ (1/4) K9s 실행을 위한 kubeconfig 설정을 진행합니다."
# K3s가 이미 설치되어 있다고 가정하고 kubeconfig 파일만 복사
if [ -f "/etc/rancher/k3s/k3s.yaml" ]; then
    mkdir -p ~/.kube
    sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
    sudo chown $(id -u):$(id -g) ~/.kube/config
    echo "kubeconfig 설정이 완료되었습니다."
else
    echo "❌ 오류: /etc/rancher/k3s/k3s.yaml 파일을 찾을 수 없습니다."
    echo "이 스크립트는 K3s Control-Plane에서 실행해야 합니다."
    exit 1
fi
echo "-----------------------------------------------------"


echo "✅ (2/4) 프로파일링 컴포넌트 설정을 진행합니다..."
# git clone은 이미 되어있다고 가정
cd SDI-Orchestration/Metric-Collector/

echo "❗ 중요: Metric-Collector-deploy.yaml 파일을 수정해야 합니다."
echo "새 터미널을 열고 아래 명령어로 파일을 열어주세요."
echo "vi SDI-Orchestration/Metric-Collector/Metric-Collector-deploy.yaml"
echo "파일의 12, 13, 21, 22행의 주석을 참고하여 id와 pw를 설정하세요."
read -p "수정이 완료되었으면 Enter를 누르세요..."

echo "프로파일링 컴포넌트를 배포합니다..."
kubectl apply -f Metric-Collector-deploy.yaml
echo "배포가 시작되었습니다. 'k9s -n tbot-monitoring'으로 상태를 확인하세요."
echo "-----------------------------------------------------"

echo "정책엔진 및 분석엔진 실행"
cd ../..  # 원래 디렉토리로 돌아가기
kubectl apply -f SDI-Orchestration/MALE-Advisor/MALE-Advisor-deploy.yaml
kubectl apply -f SDI-Orchestration/MALE-Profiler/MALE-Profiler-deploy.yaml

echo "✅ (3/4) 스케줄러 컴포넌트 설정을 준비합니다..."
cd SDI-Orchestration/SDI-Scheduler/
echo "스케줄러 컴포넌트를 배포하기 전, InfluxDB 토큰이 필요합니다."
echo "-----------------------------------------------------"

echo "✅ (4/4) 다음 단계를 안내합니다."
CONTROL_PLANE_IP=$(hostname -I | awk '{print $1}')
echo "이제 스크립트가 종료됩니다. 아래의 수동 절차를 따라주세요."
echo ""
echo "1. 웹 브라우저에서 InfluxDB UI에 접속하세요: http://${CONTROL_PLANE_IP}:32086"
echo "2. 방금 설정한 ID/PW로 로그인하세요."
echo "3. 가이드 문서의 이미지대로 'Operator's Token'을 복사하세요."
echo "4. 아래 명령어로 스케줄러 배포 파일을 여세요."
echo "   vi SDI-Orchestration/SDI-Scheduler/SDI-Scheduler-deploy.yaml"
echo "5. 43행의 주석을 참고하여 복사한 토큰 값을 붙여넣으세요."
echo "6. 수정이 완료되면, 'kubectl apply -f SDI-Orchestration/SDI-Scheduler/SDI-Scheduler-deploy.yaml' 명령어로 스케줄러를 배포하세요."
echo ""
echo "스크립트가 성공적으로 완료되었습니다."
