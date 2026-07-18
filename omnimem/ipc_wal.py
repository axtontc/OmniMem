import json
import os
import time
import uuid
from typing import Any, Callable

from omnimem.exceptions import IPCWALError

# OS-level file locking wrapper
if os.name == "nt":
    import msvcrt

    def lock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def unlock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def lock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def unlock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class AsyncWAL:
    def __init__(self, wal_dir: str):
        self.wal_dir = wal_dir
        os.makedirs(self.wal_dir, exist_ok=True)

    def execute_with_lock(self, task_name: str, payload: dict, operation: Callable) -> Any:
        # Generate idempotent key
        idempotency_key = payload.get("idempotency_key") or str(uuid.uuid4())
        lock_path = os.path.join(self.wal_dir, f"{idempotency_key}.lock")

        # Implement exponential backoff for lock
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            try:
                # Open for appending (if it doesn't exist, it gets created)
                # But to lock we usually open read/write or append
                with open(lock_path, "ab") as f:
                    lock_file(f)
                    try:
                        # Append to WAL
                        wal_path = os.path.join(self.wal_dir, f"{task_name}_wal.log")
                        with open(wal_path, "ab") as wal_f:
                            wal_f.write(
                                (
                                    json.dumps({"key": idempotency_key, "payload": payload, "status": "STARTED"})
                                    + "\\n"
                                ).encode("utf-8")
                            )

                        # Execute operation
                        result = operation()

                        with open(wal_path, "ab") as wal_f:
                            wal_f.write(
                                (json.dumps({"key": idempotency_key, "status": "COMPLETED"}) + "\\n").encode("utf-8")
                            )
                        return result
                    finally:
                        unlock_file(f)
            except (IOError, OSError) as e:
                if attempt == max_retries - 1:
                    raise IPCWALError(f"Failed to acquire lock after {max_retries} attempts: {e}")
                time.sleep(base_delay * (2**attempt))
