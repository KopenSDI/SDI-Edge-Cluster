#!/bin/bash
echo "전진 시작 (점진적 가속)"
for speed in $(seq 0.02 0.02 0.10); do
  ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
    "{linear: {x: $speed, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" > /dev/null 2>&1
  sleep 0.05
done

echo "최대 속도 유지 (2초)"
for i in {1..20}; do
  ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
    "{linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" > /dev/null 2>&1
  sleep 0.1
done

echo "감속"
for speed in $(seq 0.10 -0.02 0.0); do
  ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
    "{linear: {x: $speed, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" > /dev/null 2>&1
  sleep 0.05
done

echo "정지"
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
echo "완료!"

