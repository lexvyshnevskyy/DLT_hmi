#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${WORKSPACE:-$HOME/ros2_delatometry}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
VENV_DIR="${VENV_DIR:-$HOME/venvs/ros2_delatometry_webui}"
PACKAGE_NAME="hmi"

echo "[hmi install] workspace: $WORKSPACE"
echo "[hmi install] ROS setup:  $ROS_SETUP"
echo "[hmi install] venv:       $VENV_DIR"

if [ ! -d "$WORKSPACE/src/$PACKAGE_NAME" ]; then
  echo "ERROR: package directory not found: $WORKSPACE/src/$PACKAGE_NAME"
  exit 1
fi

if [ ! -f "$ROS_SETUP" ]; then
  echo "ERROR: ROS setup file not found: $ROS_SETUP"
  exit 1
fi

echo "[hmi install] installing apt dependencies"
sudo apt update
sudo apt install -y \
  python3-venv \
  python3-pip \
  python3-dev \
  build-essential \
  python3-serial \
  python3-psutil \
  wireless-tools \
  net-tools

echo "[hmi install] creating/updating venv"
python3 -m venv --system-site-packages "$VENV_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r "$WORKSPACE/src/hmi/requirements.txt"

echo "[hmi install] ensuring serial permissions"
if command -v usermod >/dev/null 2>&1; then
  sudo usermod -aG dialout "$USER" || true
fi

echo "[hmi install] checking known E720 lowercase field compatibility"
if grep -R "msg\.OffSet\|msg\.Level\|msg\.Freq\|msg\.FirstValue\|msg\.SecondValue" \
  "$WORKSPACE/src/hmi/hmi_rs232" >/dev/null 2>&1; then
  echo "ERROR: HMI still appears to use old uppercase E720 message field names."
  echo "Fix hmi_rs232/hmi_e720.py to read lowercase fields: offset, level, freq, firstvalue, secondvalue, etc."
  exit 2
fi

echo "[hmi install] sourcing ROS"
set +u
# shellcheck disable=SC1090
source "$ROS_SETUP"
set -u

echo "[hmi install] cleaning old hmi build/install"
rm -rf "$WORKSPACE/build/hmi" "$WORKSPACE/install/hmi"

echo "[hmi install] building hmi"
cd "$WORKSPACE"
colcon build --symlink-install --packages-select hmi

echo "[hmi install] sourcing workspace"
set +u
# shellcheck disable=SC1090
source "$WORKSPACE/install/setup.bash"
set -u

echo "[hmi install] verifying Python dependencies and ROS interfaces"
python3 -c "import serial; print('pyserial OK')"
python3 -c "import psutil; print('psutil OK')"
python3 -c "from database.srv import Query; print('database/srv/Query OK')"
python3 -c "from msgs.msg import Ads, E720; print('msgs Ads/E720 OK')"
python3 -c "import hmi_rs232.hmi_control; print('hmi_rs232.hmi_control import OK')"

echo "[hmi install] verifying ROS executable"
if ! ros2 pkg executables hmi | grep -qE '^hmi[[:space:]]+run$'; then
  echo "ERROR: expected executable not found: hmi run"
  echo "Current executables:"
  ros2 pkg executables hmi || true
  exit 3
fi

echo
echo "[hmi install] OK"
echo
echo "Start HMI manually:"
echo "  cd $WORKSPACE"
echo "  source $ROS_SETUP"
echo "  source $WORKSPACE/install/setup.bash"
echo "  source $VENV_DIR/bin/activate"
echo "  ros2 launch hmi hmi.launch.py port:=/dev/ttyS0 baudrate:=115200"
echo
echo "If using USB serial display:"
echo "  ros2 launch hmi hmi.launch.py port:=/dev/ttyUSB0 baudrate:=115200"
echo
echo "NOTE: if this is the first time adding '$USER' to dialout, log out/in or reboot before accessing /dev/ttyUSB*."
