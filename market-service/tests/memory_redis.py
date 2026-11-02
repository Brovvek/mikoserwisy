from redis.exceptions import ConnectionError


class MemoryRedis:
    """Zamiennik Redis z paczki LAB2 (tests/test_storage.py). Nie symuluje upływu TTL."""

    def __init__(self):
        self.values = {}
        self.expirations = {}
        self.down = False

    def check(self):
        if self.down:
            raise ConnectionError("Simulated outage")

    def get(self, key):
        self.check()
        return self.values.get(key)

    def set(self, key, value, ex):
        self.check()
        self.values[key] = value
        self.expirations[key] = ex

    def delete(self, key):
        self.check()
        self.values.pop(key, None)
        self.expirations.pop(key, None)

    def ping(self):
        self.check()
        return True

    def close(self):
        pass
