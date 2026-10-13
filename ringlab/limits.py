"""Bound requests before reading uploads; timed-out CPU work retains its slot."""
from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor


class BusyError(Exception):
    pass


class RateLimiter:
    """Per-client sliding windows; refuse new identities when the table is full."""
    def __init__(self, max_clients=4096, clock=time.monotonic):
        self.max_clients = max_clients
        self.clock = clock
        self.clients = OrderedDict()

    def allow(self, client, route, limit):
        now = self.clock()
        while self.clients and next(iter(self.clients.values()))[0] <= now - 60:
            self.clients.popitem(last=False)
        if client not in self.clients:
            if len(self.clients) >= self.max_clients:
                return False
            self.clients[client] = (now, {})
        _, routes = self.clients[client]
        timestamps = [t for t in routes.get(route, []) if t > now - 60]
        routes[route] = timestamps
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        self.clients[client] = (now, routes)
        self.clients.move_to_end(client)
        return True


class BoundedPool:
    """All counters are owned by one ASGI event loop, including completions."""
    def __init__(self, workers, queue, name):
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=name)
        self.capacity = workers + queue
        self.pending = 0
        self.tasks = set()
        self.closed = False

    def reserve(self):
        if self.closed or self.pending >= self.capacity:
            raise BusyError
        self.pending += 1

    def release(self):
        self.pending -= 1

    def submit(self, function, query):
        future = asyncio.get_running_loop().run_in_executor(self.executor, function, query)
        self.tasks.add(future)

        def complete(done):
            self.tasks.discard(done)
            self.release()
            if not done.cancelled():
                done.exception()

        future.add_done_callback(complete)
        return future

    async def close(self):
        self.closed = True
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.executor.shutdown(wait=True, cancel_futures=True)
