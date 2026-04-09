class E720View:
    def __init__(self) -> None:
        self.data_ready = None
        self.msg = None
        self.screen = 0

    def parse_message(self):
        if self.msg is None:
            return {}
        return {
            'OffSet': self._field(self.msg, 'OffSet'),
            'Level': self._field(self.msg, 'Level'),
            'Freq': self._field(self.msg, 'Freq'),
            'Freq10': self._field(self.msg, 'Freq10'),
            'Frequency': self._field(self.msg, 'Frequency'),
            'Limit': self._field(self.msg, 'Limit'),
            'ImParam': self._field(self.msg, 'ImParam'),
            'SecParam': self._field(self.msg, 'SecParam'),
            'SecValue': self._field(self.msg, 'SecValue'),
            'SecValue10': self._field(self.msg, 'SecValue10'),
            'SecondValue': self._field(self.msg, 'SecondValue'),
            'ImValue': self._field(self.msg, 'ImValue'),
            'ImValue10': self._field(self.msg, 'ImValue10'),
            'FirstValue': self._field(self.msg, 'FirstValue'),
            'OnChange': self._field(self.msg, 'OnChange'),
            'TimeStamp': self._field(self.msg, 'TimeStamp'),
        }

    @staticmethod
    def _field(msg, name):
        value = getattr(msg, name, 0)
        return getattr(value, 'data', value)

    def process_screen(self, screen: bytes = b'0', data=None):
        if data is None:
            data = {}
        if screen == b'0':
            return {
                'e71.txt': data.get('ImParam', 0),
                'e72.txt': data.get('FirstValue', 0),
                'e73.txt': data.get('SecParam', 0),
                'e74.txt': data.get('SecondValue', 0),
            }
        if screen == b'2':
            return {
                'e71.txt': data.get('ImParam', 0),
                'e72.txt': self.format_frequency(data.get('FirstValue', 0), ''),
                'e73.txt': '',
                'e74.txt': data.get('SecParam', 0),
                'e75.txt': round(data.get('SecondValue', 0), 4),
                'e77.txt': data.get('Limit', 0),
                'e78.txt': f"{data.get('Level', 0):.2f}v",
                'e79.txt': self.format_frequency(data.get('Frequency', 0), 'Hz'),
                'e7a.txt': f"{data.get('OffSet', 0):.2f}v",
            }
        return {}

    @staticmethod
    def format_frequency(value, dimension):
        if value < 1000:
            return f"{value:.0f} {dimension}"
        if value < 1000000:
            return f"{value / 1000:.0f} k{dimension}"
        return f"{value / 1000000:.0f} M{dimension}"
