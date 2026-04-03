from app.parsers.pvpm.parser_v5 import parse_sui_bytes

class MeasurementService:
    def __init__(self):
        self._items = []

    def list_all(self):
        return self._items

    def parse_sui_bytes(self, raw: bytes, filename: str):
        parsed = parse_sui_bytes(raw, filename)
        self._items.append(parsed)
        return parsed
