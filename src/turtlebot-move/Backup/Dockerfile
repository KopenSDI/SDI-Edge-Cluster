FROM ros:humble-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-geometry-msgs \
    ros-humble-ros2cli \
    ros-humble-ros2topic \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY smooth_move.sh /app/smooth_move.sh
RUN chmod +x /app/smooth_move.sh

ENV ROS_DOMAIN_ID=32
ENV ROS_LOCALHOST_ONLY=0
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp

SHELL ["/bin/bash", "-lc"]
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

ENTRYPOINT ["bash", "-lc", "source /opt/ros/humble/setup.bash && /app/smooth_move.sh"]

