# 멀티 아키텍처 빌드를 위한 빌드 인자
ARG TARGETPLATFORM
ARG TARGETARCH
ARG BUILDPLATFORM

FROM --platform=$TARGETPLATFORM osrf/ros:humble-desktop

# 디버깅을 위한 현재 빌드 플랫폼 출력
RUN echo "Building for: ${TARGETPLATFORM} (${TARGETARCH}), build host: ${BUILDPLATFORM}"

RUN set -eux; \
    apt-get update; \
    apt-get install -y \
        terminator \
        x11-apps \
        git \
        python3-colcon-common-extensions \
        ros-humble-cartographer \
        ros-humble-cartographer-ros \
        ros-humble-navigation2 \
        ros-humble-nav2-bringup; \
    if apt-cache show ros-humble-gazebo-ros-pkgs >/dev/null 2>&1; then \
        apt-get install -y ros-humble-gazebo-ros-pkgs; \
    else \
        echo "Skipping ros-humble-gazebo-ros-pkgs (package not available for ${TARGETARCH})"; \
    fi; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /root/turtlebot3_ws
RUN git clone -b humble https://github.com/ROBOTIS-GIT/DynamixelSDK.git src/DynamixelSDK && \
    git clone -b humble https://github.com/ROBOTIS-GIT/turtlebot3_msgs.git src/turtlebot3_msgs && \
    git clone -b humble https://github.com/ROBOTIS-GIT/turtlebot3.git src/turtlebot3 && \
    /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build --symlink-install"

RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
    echo "source /usr/share/gazebo/setup.sh" >> ~/.bashrc && \
    echo "source /root/turtlebot3_ws/install/setup.bash" >> ~/.bashrc && \
    echo 'export ROS_DOMAIN_ID=32 #TURTLEBOT3' >> ~/.bashrc

RUN echo '#!/bin/bash' > /root/run_cartographer.sh && \
    echo 'set -e' >> /root/run_cartographer.sh && \
    echo 'source /root/turtlebot3_ws/install/setup.bash' >> /root/run_cartographer.sh && \
    echo 'export TURTLEBOT3_MODEL=burger' >> /root/run_cartographer.sh && \
    echo 'ros2 launch turtlebot3_cartographer cartographer.launch.py' >> /root/run_cartographer.sh && \
    chmod +x /root/run_cartographer.sh

CMD ["/root/run_cartographer.sh"]


