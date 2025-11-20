# NotReady 노드 복구 가이드

## 문제 상황
- 노드 상태: `NotReady`
- 원인: "Kubelet stopped posting node status"
- 의미: k3s-agent가 control-plane과 통신하지 못함

## 해결 방법

### 방법 1: k3s-agent 재시작 (권장)

**turtlebot-burger-3 노드에 SSH 접속 후:**

```bash
# k3s-agent 상태 확인
sudo systemctl status k3s-agent

# k3s-agent 재시작
sudo systemctl restart k3s-agent

# 상태 확인
sudo systemctl status k3s-agent

# 로그 확인 (문제가 있다면)
sudo journalctl -u k3s-agent -n 50 --no-pager
```

**Control-plane에서 확인:**
```bash
kubectl get nodes -w
```

### 방법 2: 노드 재등록

**turtlebot-burger-3 노드에서:**

```bash
# 1. k3s-agent 중지
sudo systemctl stop k3s-agent

# 2. Control-plane에서 토큰 가져오기 (keti-csm에서 실행)
# sudo cat /var/lib/rancher/k3s/server/node-token

# 3. turtlebot-burger-3에서 토큰과 IP 설정
export K3S_TOKEN="<위에서 복사한 토큰>"
export K3S_URL="https://10.0.0.39:6443"  # keti-csm IP

# 4. k3s-agent 재설치
curl -sfL https://get.k3s.io | K3S_URL=${K3S_URL} K3S_TOKEN=${K3S_TOKEN} sh -

# 또는 기존 설치가 있다면
sudo systemctl start k3s-agent
```

### 방법 3: 자동 복구 스크립트 사용

**turtlebot-burger-3 노드에서:**

```bash
# 스크립트 복사 (control-plane에서)
scp scripts/etri-setup/k3s/fix-notready-node.sh root@10.0.0.201:/tmp/

# turtlebot-burger-3에서 실행
sudo bash /tmp/fix-notready-node.sh
```

## 빠른 진단 명령어

**Control-plane에서:**
```bash
# 노드 상태 확인
kubectl get nodes
kubectl describe node turtlebot-burger-3

# 네트워크 연결 확인
ping 10.0.0.201
nc -zv 10.0.0.201 10250

# 노드의 Pod 확인
kubectl get pods -A -o wide | grep turtlebot-burger-3
```

**turtlebot-burger-3 노드에서:**
```bash
# k3s-agent 상태
sudo systemctl status k3s-agent

# 네트워크 연결 확인
ping 10.0.0.39  # control-plane IP
nc -zv 10.0.0.39 6443

# k3s 프로세스 확인
ps aux | grep k3s
```

## 예상 원인

1. **k3s-agent 서비스 중지됨**
   - 해결: `sudo systemctl restart k3s-agent`

2. **네트워크 연결 문제**
   - 해결: 네트워크 설정 확인, 방화벽 확인

3. **토큰 만료 또는 변경**
   - 해결: 노드 재등록

4. **리소스 부족**
   - 해결: 메모리/디스크 공간 확인

## 참고

- 노드가 NotReady 상태여도 기존 Pod는 계속 실행될 수 있습니다
- 노드 재등록 시 기존 Pod는 영향받지 않습니다
- k3s-agent는 자동으로 재연결을 시도합니다

