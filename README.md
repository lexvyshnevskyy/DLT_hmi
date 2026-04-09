# hmi ROS 2 port

This is a best-effort ROS 2 port of the original ROS 1 `hmi` package.

## What changed
- `catkin` -> `ament_python`
- `rospy` -> `rclpy`
- XML launch -> ROS 2 Python launch
- script entry point -> `console_scripts`
- ROS 1 subscribers/service proxy -> ROS 2 subscriptions/client
- ad-hoc repeating timer -> ROS 2 timers

## Important assumptions
- The custom interface packages `msgs` and `database` already exist in the ROS 2 workspace.
- The service type still exposes `request` and `response` string fields.
- The message names may be `Ads` / `E720` in ROS 2. The code also includes a fallback for lowercase legacy names.

## Bookworm note
For Debian 12 Bookworm, ROS 2 is typically used via source builds on Debian or via a target platform that explicitly lists Bookworm support, depending on the ROS 2 distribution you choose.

## Build
```bash
mkdir -p ~/ros2_ws/src
cp -r hmi ~/ros2_ws/src/
cd ~/ros2_ws
source /opt/ros/<your_distro>/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select hmi
source install/setup.bash
ros2 launch hmi hmi.launch.py
```
