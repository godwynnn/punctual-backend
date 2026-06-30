import queue
import threading

class SSEManager:
    def __init__(self):
        self.listeners = {} # org_id -> list of queues
        self.lock = threading.Lock()

    def register(self, org_id):
        q = queue.Queue(maxsize=10)
        with self.lock:
            if org_id not in self.listeners:
                self.listeners[org_id] = []
            self.listeners[org_id].append(q)
        return q

    def unregister(self, org_id, q):
        with self.lock:
            if org_id in self.listeners:
                if q in self.listeners[org_id]:
                    self.listeners[org_id].remove(q)
                if not self.listeners[org_id]:
                    del self.listeners[org_id]

    def notify(self, org_id, data):
        with self.lock:
            if org_id in self.listeners:
                for q in self.listeners[org_id]:
                    try:
                        q.put_nowait(data)
                    except queue.Full:
                        pass

sse_manager = SSEManager()
