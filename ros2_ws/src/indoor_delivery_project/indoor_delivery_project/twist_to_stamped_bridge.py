import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped


class TwistToStampedBridge(Node):
    def __init__(self):
        super().__init__('twist_to_stamped_bridge')

        self.declare_parameter('input_topic', '/cmd_vel')
        self.declare_parameter(
            'output_topic',
            '/robot/diff_drive_controller/cmd_vel'
        )
        self.declare_parameter('frame_id', 'base_link')

        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value
        self.frame_id = self.get_parameter('frame_id').value

        self.sub = self.create_subscription(
            Twist,
            input_topic,
            self.cmd_callback,
            10
        )

        self.pub = self.create_publisher(
            TwistStamped,
            output_topic,
            10
        )

        self.get_logger().info(
            f'Bridging Twist {input_topic} -> TwistStamped {output_topic}'
        )

    def cmd_callback(self, msg: Twist) -> None:
        stamped = TwistStamped()
        stamped.header.stamp = self.get_clock().now().to_msg()
        stamped.header.frame_id = self.frame_id
        stamped.twist = msg
        self.pub.publish(stamped)


def main(args=None):
    rclpy.init(args=args)
    node = TwistToStampedBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()