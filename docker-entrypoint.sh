#!/usr/bin/env bash

set -e

source /opt/ros/humble/setup.bash
source /opt/stt_ws/install/setup.bash

exec "$@"
