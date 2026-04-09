import json
import socket
import subprocess
import threading
import time
from concurrent.futures import TimeoutError
from typing import Dict, Optional

import psutil
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.task import Future

from hmi_rs232.hmi_e720 import E720View
from hmi_rs232.rsconnector import RSConnector

# Try ROS 2-style CamelCase interfaces first, then fall back to legacy names.
try:
    from database.srv import Query
except ImportError:  # pragma: no cover
    from database.srv import query as Query  # type: ignore

try:
    from msgs.msg import Ads, E720
except ImportError:  # pragma: no cover
    from msgs.msg import ads as Ads  # type: ignore
    from msgs.msg import e720 as E720  # type: ignore


class NetTools:
    @staticmethod
    def get_interfaces_info() -> Dict[str, Dict[str, Optional[str]]]:
        interfaces_info: Dict[str, Dict[str, Optional[str]]] = {}

        for interface, addrs in psutil.net_if_addrs().items():
            info = {'ipv4': None, 'ipv6': None, 'ssid': None}

            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address != '127.0.0.1':
                    info['ipv4'] = addr.address
                elif addr.family == socket.AF_INET6 and not addr.address.startswith('fe80'):
                    info['ipv6'] = addr.address.split('%')[0]

            try:
                ssid = subprocess.check_output(
                    ['iwgetid', interface, '--raw'],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
                if ssid:
                    info['ssid'] = ssid
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

            if any(info.values()):
                interfaces_info[interface] = info

        return interfaces_info


class HmiProtocolMixin:
    def handle_page(self, val: bytes):
        self.page = val
        if val == b'3':
            self.get_logger().info('Loading all programs from database')
            self.handle_program_all_list()

    def handle_new_program(self, val: bytes):
        self.get_logger().info(f'New program request: {val!r}')
        response = self._process_database_query('new_program', {})
        if response.get('result') == 'Ok':
            result = self.handle_program_load_by_id(response.get('ID'))
            if result:
                self.hmi_set_datalist('pLdata0.insert', result.get('row'))

    def handle_program_load_by_id(self, val: int):
        response = self._process_database_query('get_program_by_id', {'id': int(val)})
        if response.get('result') == 'Ok':
            return response
        return None

    def handle_program_all_list(self):
        self.hmi_set_raw_command('pLdata0.clear()')
        response = self._process_database_query('program_all_list', {})
        if response.get('result') == 'Ok':
            for row in response.get('row', []):
                self.hmi_set_datalist('pLdata0.insert', row)
        return None

    def handle_program_delete_by_id(self, val: int):
        response = self._process_database_query('program_delete_by_id', {'id': int(val)})
        if response.get('result') == 'Ok':
            return response
        return None

    def handle_program_load_temp_steps(self, val: int):
        self.hmi_set_raw_command('pVdata0.clear()')
        response = self._process_database_query('program_step_list', {'id': int(val)})
        if response.get('result') == 'Ok':
            for row in response.get('row', []):
                self.hmi_set_datalist('pVdata0.insert', row)
        return None

    def handle_program_insert_temp(self, val: bytes):
        parts = val.decode().split('^')
        data = dict(zip(['program_id', 't_start', 't_stop', 'minutes'], list(map(int, parts))))
        response = self._process_database_query('program_step_insert', data)
        if response.get('result') == 'Ok':
            parts[0] = str(response['Id'])
            self.hmi_set_datalist('pVdata0.insert', '^'.join(parts))

    def handle_program_delete_temp(self, val: int):
        response = self._process_database_query('program_delete_temp', {'id': int(val)})
        if response.get('result') == 'Ok':
            return response
        self.handle_program_all_list()
        return None

    def handle_program_update_temp(self, val: bytes):
        parts = val.decode().split('^')
        data = dict(zip(['program_id', 'id', 't_start', 't_stop', 'minutes'], list(map(int, parts))))
        self._process_database_query('program_step_update', data)

    def handle_program_e7_20(self, val: bytes):
        parts = val.decode().split('^')
        id_val = int(parts[0])
        param_val = int(parts[1])
        config = list(map(int, parts[2:]))
        response = self._process_database_query(
            'set_e720', {'id': id_val, 'param': param_val, 'config': config}
        )
        if response.get('result') == 'Ok':
            return response
        return None

    def handle_get_program_e7_20(self, val: bytes):
        response = self._process_database_query('get_e720', {'id': val.decode()})
        if response.get('result') == 'Ok':
            data = response.get('row', {})
            self.hmi_set_raw_command(f"pEsw{data.get('param', 0)}.val=1")
            for idx, item in enumerate(data.get('config', [])):
                self.hmi_set_raw_command(f'pEc{idx}.val={item}')
        return None


class HmiControlNode(Node, HmiProtocolMixin):
    def __init__(self):
        super().__init__('hmi')

        self.declare_parameter('endpoint', 'hmi')
        self.declare_parameter('publish_rate', 4.0)
        self.declare_parameter('port', '/dev/ttyS0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('ads_topic', '/ads1256')
        self.declare_parameter('measure_topic', '/measure_device')
        self.declare_parameter('database_service', '/database/query')

        self.endpoint = self.get_parameter('endpoint').get_parameter_value().string_value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.port = self.get_parameter('port').get_parameter_value().string_value
        self.baudrate = int(self.get_parameter('baudrate').value)
        self.ads_topic = self.get_parameter('ads_topic').get_parameter_value().string_value
        self.measure_topic = self.get_parameter('measure_topic').get_parameter_value().string_value
        self.database_service_name = self.get_parameter('database_service').get_parameter_value().string_value

        self.ads_msg = None
        self.ads_data_ready = None
        self.data_ready = None
        self.hmi_message = None
        self.page = None
        self._stop_event = threading.Event()

        self.command_dispatch = {
            b'\x20': self.handle_page,
            b'\x51': self.handle_program_load_by_id,
            b'\x52': self.handle_program_delete_by_id,
            b'\x53': self.handle_new_program,
            b'\x54': self.handle_program_load_temp_steps,
            b'\x55': self.handle_program_insert_temp,
            b'\x56': self.handle_program_delete_temp,
            b'\x57': self.handle_program_update_temp,
            b'\x58': self.handle_get_program_e7_20,
            b'\x59': self.handle_program_e7_20,
        }

        self.connector = RSConnector(port=self.port, speed=self.baudrate)
        self.measure = E720View()

        self.ads_sub = self.create_subscription(Ads, self.ads_topic, self._ads_callback, 10)
        self.measure_sub = self.create_subscription(E720, self.measure_topic, self._e720_callback, 10)

        self.database_client = self.create_client(Query, self.database_service_name)
        while not self.database_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info(f'Waiting for database service: {self.database_service_name}')

        self._sender_timer = self.create_timer(0.25, self._controller_sender_once)
        self._waveform_timer = self.create_timer(1.0, self._waveform)

        self._poller_thread = threading.Thread(target=self._controller_poller, daemon=True)
        self._poller_thread.start()

        self.hmi_init_screen()

    def destroy_node(self):
        self._stop_event.set()
        try:
            self.connector.close()
        except Exception:
            pass
        super().destroy_node()

    def _controller_poller(self):
        buffer = bytearray()
        while rclpy.ok() and not self._stop_event.is_set():
            try:
                if self.connector.ser and self.connector.ser.in_waiting:
                    buffer += self.connector.ser.read(self.connector.ser.in_waiting)
                    while True:
                        start = buffer.find(b'\x01')
                        if start == -1 or len(buffer) - start < 6:
                            break
                        if buffer[start + 2] != 0x02:
                            buffer = buffer[start + 1:]
                            continue
                        try:
                            etx_index = buffer.index(0x03, start + 3)
                            if etx_index + 1 >= len(buffer) or buffer[etx_index + 1] != 0x04:
                                buffer = buffer[start + 1:]
                                continue
                        except ValueError:
                            break

                        end = etx_index + 2
                        self.hmi_message = bytes(buffer[start:end])
                        self.hmi_parse_response()
                        buffer = buffer[end:]
                time.sleep(0.01)
            except Exception as exc:
                self.get_logger().warning(f'Poller exception: {exc}')
                time.sleep(0.05)

    def _controller_sender_once(self):
        try:
            self.data_ready = {**(self.ads_data_ready or {}), **(self.measure.data_ready or {})}
            if self.data_ready:
                self.process_data()
                self.data_ready = None
        except Exception as exc:
            self.get_logger().warning(f'Sender exception: {exc}')

    def _ads_callback(self, msg):
        self.ads_msg = msg
        self.ads_data_ready = self.parse_ads_message(self.page, msg)

    def _waveform(self):
        if self.ads_msg and self.page == b'0':
            ch0 = self._field(self.ads_msg, 'ch0')
            ch1 = self._field(self.ads_msg, 'ch1')
            temp1 = int(ch0 * 100) + 250
            temp2 = int(ch1 * 100) + 250
            self.hmi_set_raw_command(f'add 14,0,{temp1}')
            self.hmi_set_raw_command(f'add 14,1,{temp2}')
            self.hmi_set_raw_command(f'add 14,2,{int(ch1)}')

    def _e720_callback(self, msg):
        self.measure.msg = msg
        self.measure.data_ready = self.measure.process_screen(self.page, self.measure.parse_message())

    def _process_database_query(self, command: str, params_dict: dict):
        try:
            payload = json.dumps({'cmd': command, **params_dict})
            request = Query.Request()
            request.request = payload
            future = self.database_client.call_async(request)
            response = self._wait_for_future(future, timeout_sec=5.0)
            return json.loads(response.response)
        except TimeoutError:
            self.get_logger().error('Database service call timed out')
            return {}
        except json.JSONDecodeError as exc:
            self.get_logger().error(f'Invalid JSON response: {exc}')
            return {}
        except Exception as exc:
            self.get_logger().error(f'Database service call failed: {exc}')
            return {}

    def _wait_for_future(self, future: Future, timeout_sec: float):
        start = time.monotonic()
        while rclpy.ok() and not future.done():
            if time.monotonic() - start > timeout_sec:
                raise TimeoutError()
            time.sleep(0.01)
        return future.result()

    @staticmethod
    def _field(msg, name, default=0.0):
        value = getattr(msg, name, default)
        return getattr(value, 'data', value)

    def parse_ads_message(self, page: bytes = b'0', msg=None):
        if page == b'0' and msg is not None:
            ch2 = self._field(msg, 'ch2')
            return {
                'ain0.txt': f"{self._field(msg, 'ch0'):.5f}",
                'ain1.txt': f"{self._field(msg, 'ch1'):.5f}",
                'ain2.txt': f'{ch2:.2f}/{(ch2 - 273.15):.2f}',
            }
        return {}

    def process_data(self):
        for key, value in self.data_ready.items():
            time.sleep(0.01)
            self.hmi_set_variable(key, value)

    def hmi_parse_response(self):
        try:
            msg = self.hmi_message
            if not msg or len(msg) < 6:
                return
            if msg[0] != 0x01 or msg[2] != 0x02 or msg[-2] != 0x03 or msg[-1] != 0x04:
                self.get_logger().warning('Invalid message format')
                return

            cmd = bytes(msg[1:2])
            val = bytes(msg[3:-2])
            callback = self.command_dispatch.get(cmd)
            if callback:
                callback(val)
            else:
                self.get_logger().warning(f'No handler for command: {cmd!r}')
        except Exception as exc:
            self.get_logger().warning(f'Parse response failed: {exc}')

    def hmi_init_screen(self):
        self.hmi_reset()
        time.sleep(2)
        self.hmi_bkcmd(2)
        self.hmi_set_page(6)

        try:
            if self.topic_exists(self.measure_topic) and self.measure.msg:
                self.hmi_set_variable('s1.txt', 'Ready!')
        except Exception:
            self.hmi_set_variable('s1.txt', 'False')

        try:
            if self.topic_exists(self.ads_topic) and self.ads_msg:
                self.hmi_set_variable('s2.txt', 'Ready!')
        except Exception:
            self.hmi_set_variable('s2.txt', 'False')

        if self.database_client.service_is_ready():
            self.hmi_set_variable('s3.txt', 'Ready!')

        tools = NetTools()
        interfaces = tools.get_interfaces_info()
        line = ''
        for iface, data in interfaces.items():
            line += (
                f'{iface}:\r\n'
                f'\t IPv4={data["ipv4"]}\r\n'
                f'\t IPv6={data["ipv6"]}\r\n'
                f'\t SSID={data["ssid"]}\r\n'
            )

        line += '\r\n\r\nEth/Wifi default IP:\r\n\t IPv4=192.168.1.42\r\n'
        self.hmi_set_variable('slt0.txt', line)

    def topic_exists(self, topic_name: str) -> bool:
        return any(name == topic_name for name, _ in self.get_topic_names_and_types())

    def hmi_reset(self):
        return self.connector.send_encoded_message(b'rest')

    def hmi_set_page(self, page_number: int = 0):
        return self.connector.send_encoded_message(f'page {page_number}'.encode('utf-8'))

    def hmi_visible(self, element_id: int = 0, visible: int = 0):
        return self.connector.send_encoded_message(f'vis {element_id},"{visible}"'.encode('utf-8'))

    def hmi_fill(self, x0: int = 0, y0: int = 0, x1: int = 0, y1: int = 0, color: str = 'RED'):
        return self.connector.send_encoded_message(f'fill {x0},{y0},{x1},{y1},{color}'.encode('utf-8'))

    def hmi_bkcmd(self, level: int = 2):
        return self.connector.send_encoded_message(f'bkcmd={level}'.encode('utf-8'))

    def hmi_set_variable(self, variable: str = '', value=''):
        return self.connector.send_encoded_message(f'{variable}="{value}"'.encode('utf-8'))

    def hmi_set_datalist(self, variable: str = '', value: str = ''):
        return self.connector.send_encoded_message(f'{variable}("{value}")'.encode('utf-8'))

    def hmi_set_raw_command(self, command: str = ''):
        return self.connector.send_encoded_message(command.encode('utf-8'))


__all__ = ['HmiControlNode']
