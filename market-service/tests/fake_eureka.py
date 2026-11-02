class FakeEurekaClient:
    """Zamiennik klienta Eureki: liczy start i stop, nie łączy się z siecią."""

    def __init__(self, on_start=None):
        self.on_start = on_start
        self.starts = 0
        self.stops = 0

    async def start(self):
        self.starts += 1
        if self.on_start is not None:
            self.on_start()

    async def stop(self):
        self.stops += 1
