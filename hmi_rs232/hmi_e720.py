class E720View:
    def __init__(self) -> None:
        self.data_ready = None
        self.msg = None
        self.screen = 0

    def parse_message(self):
        if self.msg is None:
            return {}

        return {
            'OffSet': self._field(self.msg, 'offset'),
            'Level': self._field(self.msg, 'level'),
            'Freq': self._field(self.msg, 'freq'),
            'Freq10': self._field(self.msg, 'freq10'),
            'Frequency': self._field(self.msg, 'frequency'),
            'Limit': self._field(self.msg, 'limit'),
            'ImParam': self._field(self.msg, 'imparam'),
            'SecParam': self._field(self.msg, 'secparam'),
            'SecValue': self._field(self.msg, 'secvalue'),
            'SecValue10': self._field(self.msg, 'secvalue10'),
            'SecondValue': self._field(self.msg, 'secondvalue'),
            'ImValue': self._field(self.msg, 'imvalue'),
            'ImValue10': self._field(self.msg, 'imvalue10'),
            'FirstValue': self._field(self.msg, 'firstvalue'),
            'OnChange': self._field(self.msg, 'onchange'),
            'TimeStamp': self._field(self.msg, 'timestamp'),
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
                'e71.txt': data.get('ImParam', ''),
                'e72.txt': data.get('FirstValue', 0),
                'e73.txt': data.get('SecParam', ''),
                'e74.txt': data.get('SecondValue', 0),
            }

        if screen == b'2':
            return {
                'e71.txt': data.get('ImParam', ''),
                'e72.txt': self.format_frequency(float(data.get('FirstValue', 0) or 0), ''),
                'e73.txt': '',
                'e74.txt': data.get('SecParam', ''),
                'e75.txt': round(float(data.get('SecondValue', 0) or 0), 4),
                'e77.txt': data.get('Limit', ''),
                'e78.txt': f"{float(data.get('Level', 0) or 0):.2f}v",
                'e79.txt': self.format_frequency(float(data.get('Frequency', 0) or 0), 'Hz'),
                'e7a.txt': f"{float(data.get('OffSet', 0) or 0):.2f}v",
            }

        return {}

    @staticmethod
    def format_frequency(value, dimension):
        value = float(value or 0)
        if value < 1000:
            return f"{value:.0f} {dimension}"
        if value < 1000000:
            return f"{value / 1000:.0f} k{dimension}"
        return f"{value / 1000000:.0f} M{dimension}"
