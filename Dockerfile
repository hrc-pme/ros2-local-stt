FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV STT_MODEL_PATH=/models/faster-whisper

SHELL ["/bin/bash", "-c"]

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        python3-pip \
        ros-humble-audio-common-msgs \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir \
      "numpy>=1.24,<2" \
      "faster-whisper>=1.1.0,<2" \
      "opencc-python-reimplemented>=0.1.7,<1" \
      "webrtcvad-wheels>=2.0.14,<3"

WORKDIR /opt/stt_ws
COPY ros2_ws/src ./src

RUN source /opt/ros/humble/setup.bash \
    && colcon build --merge-install

COPY docker-entrypoint.sh /usr/local/bin/stt-entrypoint
RUN chmod +x /usr/local/bin/stt-entrypoint

ENTRYPOINT ["/usr/local/bin/stt-entrypoint"]
CMD ["ros2", "launch", "local_stt", "stt.launch.py"]
