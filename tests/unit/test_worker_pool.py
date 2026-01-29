import pytest
import asyncio
from src.processor.worker_pool import WorkerPool

@pytest.mark.asyncio
async def test_worker_pool():
    async def sample_task(data):
        return data * 2

    pool = WorkerPool(num_workers=2)

    tasks = [lambda: sample_task(i) for i in range(5)]

    await pool.run(tasks)

    # Add assertions to verify task execution if needed