import rclpy
from rclpy.executors import MultiThreadedExecutor

from hmi_rs232.hmi_control import HmiControlNode


def main(args=None):
    rclpy.init(args=args)
    node = HmiControlNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
