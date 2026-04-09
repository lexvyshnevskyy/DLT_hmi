import threading
import time
from typing import Optional

import serial


class RSConnector:
    def __init__(self, port: str = '/dev/ttyUSB0', speed: int = 115200, timeout: float = 0.1):
        self._lock = threading.Lock()
        self.ser: Optional[serial.Serial] = None
        self.ser = serial.Serial(port, speed, timeout=timeout)

    def close(self) -> None:
        with self._lock:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def send_message(self, message: bytes = b'') -> int:
        with self._lock:
            if not self.ser:
                return 0
            self.ser.flush()
            written = self.ser.write(message)
            time.sleep(0.01)
            return written

    def read_message(self) -> bytes:
        with self._lock:
            if not self.ser:
                return b''
            result = self.ser.read(self.ser.in_waiting)
            self.ser.reset_input_buffer()
            return result

    def send_encoded_message(self, message: bytes = b'') -> bytes:
        self.send_message(message + b'\xff\xff\xff')
        return self.read_message()
