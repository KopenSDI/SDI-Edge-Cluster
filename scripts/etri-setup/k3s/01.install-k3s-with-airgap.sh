#!/bin/bash

#############################################
# K3s 완전 오프라인 설치 스크립트
# USB로 가져온 파일들을 활용한 K3s 설치
# 네트워크 연결 없이 동작
#############################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 스크립트가 위치한 디렉토리 찾기
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 변수 설정
K3S_VERSION=${K3S_VERSION:-"v1.33.4+k3s1"}
ARCH=${ARCH:-"amd64"}
INSTALL_DIR="/usr/local/bin"
IMAGES_DIR="/var/lib/rancher/k3s/agent/images"
AIRGAP_FILE="${SCRIPT_DIR}/k3s-airgap-images-amd64.tar.gz"
K3S_BINARY="${SCRIPT_DIR}/k3s"
TEMP_DIR="/tmp/k3s-offline-install"

echo "======================================"
echo "K3s 오프라인 설치 스크립트"
echo "======================================"
echo ""

# root 권한 확인
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}이 스크립트는 root 권한으로 실행해야 합니다.${NC}"
    exit 1
fi

# 필수 파일 존재 확인
check_required_files() {
    echo -e "${YELLOW}📋 필수 파일 확인 중...${NC}"
    
    # Air-gap 이미지 파일 확인
    if [ ! -f "$AIRGAP_FILE" ]; then
        echo -e "${RED}❌ Air-gap 이미지 파일을 찾을 수 없습니다: $AIRGAP_FILE${NC}"
        echo "스크립트와 같은 디렉토리에 k3s-airgap-images-amd64.tar.gz 파일이 필요합니다."
        exit 1
    fi
    
    # K3s 바이너리 파일 확인
    if [ ! -f "$K3S_BINARY" ]; then
        echo -e "${RED}❌ K3s 바이너리 파일을 찾을 수 없습니다: $K3S_BINARY${NC}"
        echo "스크립트와 같은 디렉토리에 k3s 바이너리 파일이 필요합니다."
        echo ""
        echo "K3s 바이너리를 다운로드하려면:"
        echo "  wget https://github.com/k3s-io/k3s/releases/download/v1.33.4%2Bk3s1/k3s"
        echo "  chmod +x k3s"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Air-gap 이미지 파일 확인: $(basename $AIRGAP_FILE)${NC}"
    echo -e "${GREEN}✓ K3s 바이너리 파일 확인: $(basename $K3S_BINARY)${NC}"
    echo ""
}

# 네트워크 인터페이스 자동 감지
get_network_interface() {
    # 첫 번째 활성 이더넷 인터페이스 찾기
    INTERFACE=$(ip link show | grep "state UP" | grep -E "(eth|ens|enp|eno)" | head -1 | awk '{print $2}' | sed 's/:$//')

    if [ -z "$INTERFACE" ]; then
        # 기본 라우트의 인터페이스 사용
        INTERFACE=$(ip route show default 2>/dev/null | head -1 | awk '{print $5}')
    fi

    if [ -z "$INTERFACE" ]; then
        # 그래도 없으면 첫 번째 UP 인터페이스
        INTERFACE=$(ip link show | grep "state UP" | head -1 | awk '{print $2}' | sed 's/:$//')
    fi

    echo "$INTERFACE"
}

# K3s 설치
install_k3s() {
    echo -e "${YELLOW}🚀 K3s 설치 시작...${NC}"

    # 1. K3s 바이너리 설치
    echo "  - K3s 바이너리 설치 중..."
    cp "$K3S_BINARY" "$INSTALL_DIR/k3s"
    chmod +x "$INSTALL_DIR/k3s"

    # 심볼릭 링크 생성
    ln -sf "$INSTALL_DIR/k3s" "$INSTALL_DIR/kubectl"
    ln -sf "$INSTALL_DIR/k3s" "$INSTALL_DIR/crictl"
    ln -sf "$INSTALL_DIR/k3s" "$INSTALL_DIR/ctr"

    # 2. Air-gap 이미지 배치
    echo "  - Air-gap 이미지 설치 중..."
    mkdir -p "$IMAGES_DIR"
    cp "$AIRGAP_FILE" "$IMAGES_DIR/"

    # Air-gap 이미지를 직접 임포트 (pause 이미지 포함)
    echo "  - Air-gap 이미지 임포트 중..."
    if command -v k3s >/dev/null 2>&1; then
        gunzip -c "$IMAGES_DIR/k3s-airgap-images-${ARCH}.tar.gz" | k3s ctr images import - 2>/dev/null || true
    fi

    # 3. killall 스크립트 생성
    create_killall_script

    # 4. uninstall 스크립트 생성
    create_uninstall_script

    # 5. systemd 서비스 생성
    create_systemd_service

    echo -e "${GREEN}✓ K3s 설치 완료${NC}"
    echo ""
}

# killall 스크립트 생성
create_killall_script() {
    cat > /usr/local/bin/k3s-killall.sh << 'EOF'
#!/bin/bash
[ $(id -u) -eq 0 ] || exec sudo $0 $@

for bin in /var/lib/rancher/k3s/data/**/bin/; do
    [ -d $bin ] && export PATH=$PATH:$bin:$bin/aux
done

set -x

for service in /etc/systemd/system/k3s*.service; do
    [ -s $service ] && systemctl stop $(basename $service)
done

for service in /etc/init.d/k3s*; do
    [ -x $service ] && $service stop
done

pschildren() {
    ps -e -o ppid= -o pid= | sed -e 's/^\s*//g; s/\s\s*/\t/g;' | grep -w "^$1" | cut -f2
}

pstree() {
    for pid in $@; do
        echo $pid
        for child in $(pschildren $pid); do
            pstree $child
        done
    done
}

killtree() {
    kill -9 $(
        { set +x; } 2>/dev/null;
        pstree $@;
        set -x;
    ) 2>/dev/null
}

getshims() {
    ps -e -o pid= -o args= | sed -e 's/^ *//; s/\s\s*/\t/;' | grep -w 'k3s/data/[^/]*/bin/containerd-shim' | cut -f1
}

killtree $({ set +x; } 2>/dev/null; getshims; set -x)

do_unmount_and_remove() {
    awk -v path="$1" '$2 ~ ("^" path) { print $2 }' /proc/self/mounts | sort -r | xargs -r -t -n 1 sh -c 'umount "$0" && rm -rf "$0"'
}

do_unmount_and_remove '/run/k3s'
do_unmount_and_remove '/var/lib/rancher/k3s'
do_unmount_and_remove '/var/lib/kubelet/pods'
do_unmount_and_remove '/run/netns/cni-'

ip netns show 2>/dev/null | grep cni- | xargs -r -t -n 1 ip netns delete

command -v systemctl >/dev/null 2>&1 && systemctl daemon-reload
EOF
    chmod +x /usr/local/bin/k3s-killall.sh
}

# uninstall 스크립트 생성
create_uninstall_script() {
    cat > /usr/local/bin/k3s-uninstall.sh << 'EOF'
#!/bin/bash
[ $(id -u) -eq 0 ] || exec sudo $0 $@

/usr/local/bin/k3s-killall.sh

if command -v systemctl >/dev/null 2>&1; then
    systemctl disable k3s
    systemctl reset-failed k3s
    systemctl daemon-reload
fi

rm -f /etc/systemd/system/k3s.service
rm -f /etc/systemd/system/k3s.service.d/*

remove_uninstall() {
    rm -f /usr/local/bin/k3s-uninstall.sh
}
trap remove_uninstall EXIT

rm -rf /etc/rancher/k3s
rm -rf /var/lib/rancher/k3s
rm -rf /var/lib/kubelet
rm -f /usr/local/bin/k3s
rm -f /usr/local/bin/kubectl
rm -f /usr/local/bin/crictl
rm -f /usr/local/bin/ctr
rm -f /usr/local/bin/k3s-killall.sh
EOF
    chmod +x /usr/local/bin/k3s-uninstall.sh
}

# systemd 서비스 생성
create_systemd_service() {
    local interface=$(get_network_interface)

    echo "  - systemd 서비스 생성 중..."
    echo "    감지된 네트워크 인터페이스: ${interface:-자동}"

    # 기본 서비스 파일 생성
    cat > /etc/systemd/system/k3s.service << EOF
[Unit]
Description=Lightweight Kubernetes
Documentation=https://k3s.io
Wants=network-online.target
After=network-online.target

[Service]
Type=notify
EnvironmentFile=-/etc/default/%N
EnvironmentFile=-/etc/sysconfig/%N
EnvironmentFile=-/etc/systemd/system/k3s.service.env
KillMode=process
Delegate=yes
LimitNOFILE=1048576
LimitNPROC=infinity
LimitCORE=infinity
TasksMax=infinity
TimeoutStartSec=0
Restart=always
RestartSec=5s
ExecStartPre=/bin/sh -xc '! /usr/bin/systemctl is-enabled --quiet nm-cloud-setup.service'
ExecStartPre=-/sbin/modprobe br_netfilter
ExecStartPre=-/sbin/modprobe overlay
ExecStart=/usr/local/bin/k3s server --write-kubeconfig-mode=644
EOF

    # 네트워크 인터페이스가 감지되면 flannel 설정 추가
    if [ -n "$interface" ]; then
        sed -i "s|^ExecStart=.*|ExecStart=/usr/local/bin/k3s server --write-kubeconfig-mode=644 --flannel-iface=$interface|" /etc/systemd/system/k3s.service
    fi

    cat >> /etc/systemd/system/k3s.service << EOF

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
}

# K3s 시작 및 확인
start_and_verify_k3s() {
    echo -e "${YELLOW}🔧 K3s 시작 중...${NC}"

    # 서비스 활성화 및 시작
    systemctl enable k3s
    systemctl start k3s

    echo "  - K3s 서비스 시작 대기 중..."

    # 서비스 시작 확인
    local count=0
    while ! systemctl is-active --quiet k3s; do
        if [ $count -gt 60 ]; then
            echo -e "${RED}K3s 서비스 시작 실패${NC}"
            echo "다음 명령어로 로그를 확인하세요:"
            echo "  journalctl -u k3s -n 50"
            return 1
        fi
        sleep 2
        count=$((count + 2))
        echo "    대기 중... ($count/60초)"
    done

    echo -e "${GREEN}✓ K3s 서비스 실행 중${NC}"

    # Air-gap 이미지 재임포트 (서비스 시작 후)
    if [ -f "$IMAGES_DIR/k3s-airgap-images-${ARCH}.tar.gz" ]; then
        echo "  - Air-gap 이미지 최종 임포트..."
        gunzip -c "$IMAGES_DIR/k3s-airgap-images-${ARCH}.tar.gz" | k3s ctr images import - 2>/dev/null || true
    fi

    # kubeconfig 설정
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

    # API 서버 준비 대기
    echo "  - API 서버 준비 대기 중..."
    count=0
    while ! kubectl get nodes &>/dev/null; do
        if [ $count -gt 120 ]; then
            echo -e "${YELLOW}⚠ API 서버 연결 시간 초과${NC}"
            break
        fi
        sleep 3
        count=$((count + 3))
        echo "    대기 중... ($count/120초)"
    done

    echo ""
}

# 최종 상태 표시
show_final_status() {
    echo "======================================"
    echo -e "${GREEN}K3s 오프라인 설치 완료! 🎉${NC}"
    echo "======================================"
    echo ""

    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

    # K3s 버전 확인
    echo -e "${BLUE}📊 K3s 버전:${NC}"
    k3s --version | head -1
    echo ""

    # 노드 상태
    echo -e "${BLUE}📊 노드 상태:${NC}"
    kubectl get nodes -o wide 2>/dev/null || echo "노드 정보를 가져올 수 없습니다."
    echo ""

    # Pod 상태
    echo -e "${BLUE}📊 시스템 Pod 상태:${NC}"
    kubectl get pods -n kube-system 2>/dev/null || echo "Pod 정보를 가져올 수 없습니다."
    echo ""

    echo -e "${BLUE}📝 유용한 명령어:${NC}"
    echo "  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
    echo "  kubectl get nodes"
    echo "  kubectl get pods -A"
    echo "  systemctl status k3s"
    echo "  journalctl -u k3s -f"
    echo ""

    echo -e "${BLUE}📦 사용된 파일들:${NC}"
    echo "  Air-gap 이미지: $(basename $AIRGAP_FILE)"
    echo "  K3s 바이너리: $(basename $K3S_BINARY)"
    echo "  스크립트 위치: $SCRIPT_DIR"
    echo ""
}

# Docker 이미지 복사
copy_docker_images() {
    echo -e "${YELLOW}📦 Docker 이미지 복사 중...${NC}"
    
    DOCKER_IMAGES_DIR="${SCRIPT_DIR}/docker_images"
    K3S_IMAGES_DIR="/var/lib/rancher/k3s/agent/images"
    
    if [ -d "$DOCKER_IMAGES_DIR" ] && [ "$(ls -A $DOCKER_IMAGES_DIR/*.tar 2>/dev/null)" ]; then
        echo "  - 저장된 Docker 이미지들을 K3s 이미지 디렉토리에 복사 중..."
        
        # K3s 이미지 디렉토리 확인 및 생성
        if [ ! -d "$K3S_IMAGES_DIR" ]; then
            echo "    K3s 이미지 디렉토리 생성 중..."
            mkdir -p "$K3S_IMAGES_DIR"
        fi
        
        COPIED_COUNT=0
        for tar_file in "$DOCKER_IMAGES_DIR"/*.tar; do
            if [ -f "$tar_file" ]; then
                filename=$(basename "$tar_file")
                echo "    처리 중: $filename"
                
                # 이미 K3s 이미지 디렉토리에 존재하는지 확인
                if [ -f "$K3S_IMAGES_DIR/$filename" ]; then
                    echo "    ⏭️ 이미 존재: $filename"
                    COPIED_COUNT=$((COPIED_COUNT + 1))
                else
                    if cp "$tar_file" "$K3S_IMAGES_DIR/"; then
                        echo "    ✓ 복사 완료"
                        COPIED_COUNT=$((COPIED_COUNT + 1))
                    else
                        echo "    ❌ 복사 실패"
                    fi
                fi
            fi
        done
        
        echo "  - Docker 이미지 복사 완료: $COPIED_COUNT개"
        echo "  - K3s 서비스 재시작 후 이미지들이 사용 가능합니다."
    else
        echo "  - 저장된 Docker 이미지가 없습니다."
        echo "  - SDI-Orchestration 배포 시 이미지를 다운로드해야 합니다."
    fi
    echo ""
}

# 메인 실행
main() {
    echo -e "${BLUE}K3s 완전 오프라인 설치 모드${NC}"
    echo "스크립트 위치: $SCRIPT_DIR"
    echo "네트워크 연결 없이 동작합니다."
    echo ""
    
    check_required_files
    install_k3s
    start_and_verify_k3s
    copy_docker_images
    show_final_status
}

# 스크립트 실행
main "$@"
