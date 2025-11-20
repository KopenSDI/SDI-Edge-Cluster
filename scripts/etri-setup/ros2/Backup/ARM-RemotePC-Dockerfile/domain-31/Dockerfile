# ROS2 Humble 베이스 이미지 (멀티 아키텍처 지원)
FROM ros:humble-ros-base

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble

# 기본 패키지 및 의존성 설치
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    git \
    wget \
    curl \
    nano \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# ROS2 의존성 초기화
RUN rosdep update

# TurtleBot3 패키지 설치
RUN apt-get update && apt-get install -y \
    ros-humble-turtlebot3 \
    ros-humble-turtlebot3-msgs \
    ros-humble-dynamixel-sdk \
    && rm -rf /var/lib/apt/lists/*

# 워크스페이스 생성
WORKDIR /turtlebot3_ws

# TurtleBot3 환경 변수 설정
ENV TURTLEBOT3_MODEL=burger
ENV ROS_DOMAIN_ID=31

# ROS2 환경 설정 스크립트
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
    echo "export TURTLEBOT3_MODEL=burger" >> ~/.bashrc && \
    echo "export ROS_DOMAIN_ID=31" >> ~/.bashrc

# Navigation 및 Cartographer 패키지 설치
# 참고: ros-humble-gazebo-ros-pkgs는 ARM64에서 제공되지 않으므로 제외
RUN apt-get update && apt-get install -y \
    ros-humble-cartographer \
    ros-humble-cartographer-ros \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 권한 설정
RUN chmod -R 777 /turtlebot3_ws

# 컨테이너 시작시 ROS2 환경 소싱
ENTRYPOINT ["/bin/bash", "-c", "source /opt/ros/humble/setup.bash && exec \"$@\"", "--"]
CMD ["bash"]
