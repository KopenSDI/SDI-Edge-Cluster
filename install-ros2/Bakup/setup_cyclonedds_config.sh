#!/bin/bash
set -e

# 네임스페이스 생성 (이미 있으면 무시)
kubectl create ns ros || true

# ConfigMap 생성/적용
cat <<'EOF' | kubectl apply -n ros -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: cyclonedds-config
data:
  cyclonedds.xml: |
    <?xml version="1.0" encoding="UTF-8" ?>
    <CycloneDDS xmlns="https://cdds.io/config">
      <Domain id="any">
        <General>
          <NetworkInterfaceAddress>auto</NetworkInterfaceAddress>
        </General>
        <Discovery>
          <ParticipantIndex>auto</ParticipantIndex>
          <AllowMulticast>false</AllowMulticast>
          <Peers>
            <Peer address="10.0.0.39"/>   <!-- 서버랙 -->
            <Peer address="10.0.0.201"/>  <!-- 터틀봇 -->
          </Peers>
        </Discovery>
        <Transport>
          <UDP>
            <EnableMultiInterface>true</EnableMultiInterface>
            <AllowMulticast>false</AllowMulticast>
          </UDP>
        </Transport>
      </Domain>
    </CycloneDDS>
EOF

echo "✅ CycloneDDS ConfigMap이 생성/적용되었습니다 (namespace: ros)."

