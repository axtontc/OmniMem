import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Cross-platform file locking
if os.name == "nt":
    import msvcrt
else:
    try:
        import fcntl
    except ImportError:
        fcntl = None  # type: ignore


class FileLockException(Exception):
    0


class FileLock:
    """
    Cross-platform OS-level file locking with timeouts and exponential backoff.
    """

    def __init__(self, filepath: str, timeout: float = 10.0, base_backoff: float = 0.01, max_backoff: float = 0.5):
        self.filepath = filepath
        self.timeout = timeout
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self._fd = None

    def acquire(self):
        """Acquires the lock with exponential backoff."""
        start_time = time.time()
        backoff = self.base_backoff

        self._fd = os.open(self.filepath, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

        while True:
            try:
                if os.name == "nt":
                    # Windows: LK_NBLCK is non-blocking lock
                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                else:
                    # Unix: LOCK_EX | LOCK_NB for non-blocking exclusive lock
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (IOError, OSError):
                if time.time() - start_time >= self.timeout:
                    os.close(self._fd)
                    self._fd = None
                    raise FileLockException(f"Timeout acquiring lock on {self.filepath}")

                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)

    def release(self):
        """Releases the lock."""
        if self._fd is not None:
            try:
                if os.name == "nt":
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class AsyncWAL:
    """
    Write-Ahead Log with asynchronous I/O batching and idempotency guarantees.
    """

    def __init__(self, log_path: str, lock_path: str, sync_interval: float = 0.1):
        self.log_path = log_path
        self.lock_path = lock_path
        self.sync_interval = sync_interval
        self._queue: asyncio.Queue = asyncio.Queue()
        self._flush_task = None
        self._seen_txids: set = set()
        self._running = False
        self._file = None

    async def start(self):
        self._running = True
        self._load_seen_txids()
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError as e:
                logger.info(f"Flush task cancelled: {e}")
        # Flush remaining
        await self._flush_batch()

    def _load_seen_txids(self):
        """Load seen transaction IDs from the WAL to guarantee idempotency across restarts."""
        if not os.path.exists(self.log_path):
            return

        with FileLock(self.lock_path):
            with open(self.log_path, "rb") as f:
                for line in f:
                    line = line.decode("utf-8")
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        txid = entry.get("txid")
                        if txid:
                            self._seen_txids.add(txid)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse WAL entry: {e}")
                        continue

    async def append(self, entry: Dict[str, Any], txid: Optional[str] = None) -> str:
        """
        Appends an entry to the WAL. Returns the transaction ID.
        If txid is provided and already exists, it is ignored (idempotent).
        """
        if not txid:
            txid = str(uuid.uuid4())

        if txid in self._seen_txids:
            return txid  # Idempotent

        # We eagerly add to seen to prevent duplicates in memory before flush
        self._seen_txids.add(txid)

        wal_entry = {"txid": txid, "timestamp": time.time(), "data": entry}

        await self._queue.put(wal_entry)
        return txid

    async def _flush_loop(self):
        while self._running:
            await asyncio.sleep(self.sync_interval)
            await self._flush_batch()

    async def _flush_batch(self):
        if self._queue.empty():
            return

        batch = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not batch:
            return

        # Perform IO in a thread to avoid blocking event loop
        await asyncio.to_thread(self._write_batch_sync, batch)

        for _ in batch:
            self._queue.task_done()

    def _write_batch_sync(self, batch: List[Dict[str, Any]]):
        """Synchronous write with OS-level locking."""
        with FileLock(self.lock_path):
            # Open file in append mode
            with open(self.log_path, "ab") as f:
                for entry in batch:
                    f.write((json.dumps(entry) + "\n").encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
