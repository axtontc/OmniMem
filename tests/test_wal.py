import asyncio
import os
import pytest
import time
from omnimem.wal import FileLock, AsyncWAL, FileLockException
import multiprocessing

def worker_acquire_lock(lock_path: str, hold_time: float, queue: multiprocessing.Queue):
    try:
        with FileLock(lock_path, timeout=1.0):
            queue.put("ACQUIRED")
            time.sleep(hold_time)
            queue.put("RELEASED")
    except FileLockException:
        queue.put("TIMEOUT")

def test_file_lock_timeout():
    lock_path = "test.lock"
    if os.path.exists(lock_path):
        os.remove(lock_path)
    
    q1 = multiprocessing.Queue()
    q2 = multiprocessing.Queue()
    
    p1 = multiprocessing.Process(target=worker_acquire_lock, args=(lock_path, 2.0, q1))
    p2 = multiprocessing.Process(target=worker_acquire_lock, args=(lock_path, 0.5, q2))
    
    p1.start()
    # Wait for p1 to acquire
    assert q1.get(timeout=3) == "ACQUIRED"
    
    p2.start()
    # p2 should fail because p1 holds it for 2s and p2 timeout is 1s
    assert q2.get(timeout=3) == "TIMEOUT"
    
    p1.join()
    p2.join()
    
    if os.path.exists(lock_path):
        os.remove(lock_path)

@pytest.mark.asyncio
async def test_async_wal_basic():
    log_path = "test_wal.log"
    lock_path = "test_wal.lock"
    if os.path.exists(log_path):
        os.remove(log_path)
    if os.path.exists(lock_path):
        os.remove(lock_path)
        
    wal = AsyncWAL(log_path, lock_path, sync_interval=0.05)
    await wal.start()
    
    tx1 = await wal.append({"action": "create", "node": "A"})
    tx2 = await wal.append({"action": "create", "node": "B"})
    
    # Wait for flush
    await asyncio.sleep(0.2)
    
    # Verify file contents
    assert os.path.exists(log_path)
    with open(log_path, 'rb') as f:
        lines = f.read().decode('utf-8').splitlines()
        assert len(lines) == 2
        assert tx1 in lines[0]
        assert tx2 in lines[1]
        
    await wal.stop()
    
    # Test idempotency
    wal2 = AsyncWAL(log_path, lock_path, sync_interval=0.05)
    await wal2.start()
    
    # This should be ignored
    tx_dup = await wal2.append({"action": "create", "node": "A"}, txid=tx1)
    assert tx_dup == tx1
    
    await asyncio.sleep(0.2)
    with open(log_path, 'rb') as f:
        lines = f.read().decode('utf-8').splitlines()
        assert len(lines) == 2 # Still 2
        
    await wal2.stop()
    
    if os.path.exists(log_path):
        os.remove(log_path)
    if os.path.exists(lock_path):
        os.remove(lock_path)
