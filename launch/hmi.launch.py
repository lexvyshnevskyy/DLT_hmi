from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    endpoint_arg = DeclareLaunchArgument('endpoint', default_value='hmi')
    publish_rate_arg = DeclareLaunchArgument('publish_rate', default_value='4.0')
    port_arg = DeclareLaunchArgument('port', default_value='/dev/ttyS0')
    baudrate_arg = DeclareLaunchArgument('baudrate', default_value='115200')
    ads_topic_arg = DeclareLaunchArgument('ads_topic', default_value='/ads1256')
    measure_topic_arg = DeclareLaunchArgument('measure_topic', default_value='/measure_device')
    database_service_arg = DeclareLaunchArgument('database_service', default_value='/database/query')

    node = Node(
        package='hmi',
        executable='run',
        name='hmi',
        output='screen',
        parameters=[{
            'endpoint': LaunchConfiguration('endpoint'),
            'publish_rate': LaunchConfiguration('publish_rate'),
            'port': LaunchConfiguration('port'),
            'baudrate': LaunchConfiguration('baudrate'),
            'ads_topic': LaunchConfiguration('ads_topic'),
            'measure_topic': LaunchConfiguration('measure_topic'),
            'database_service': LaunchConfiguration('database_service'),
        }],
    )

    return LaunchDescription([
        endpoint_arg,
        publish_rate_arg,
        port_arg,
        baudrate_arg,
        ads_topic_arg,
        measure_topic_arg,
        database_service_arg,
        node,
    ])
