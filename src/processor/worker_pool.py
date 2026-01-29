import asyncio
from typing import Callable, Any, List

class WorkerPool:
    """
    A worker pool to manage concurrent tasks.
    """

    def __init__(self, num_workers: int):
        self.num_workers = num_workers
        self.queue = asyncio.Queue()

    async def worker(self):
        """
        A single worker that processes tasks from the queue.
        """
        while True:
            task, args, kwargs = await self.queue.get()
            try:
                await task(*args, **kwargs)
            except Exception as e:
                print(f"Task failed with error: {e}")
            finally:
                self.queue.task_done()

    async def add_task(self, task: Callable[..., Any], *args, **kwargs):
        """
        Adds a task to the queue.

        Args:
            task (Callable[..., Any]): The coroutine function to execute.
            *args: Positional arguments for the task.
            **kwargs: Keyword arguments for the task.
        """
        await self.queue.put((task, args, kwargs))

    async def run(self, tasks: List[Callable[..., Any]]):
        """
        Runs the worker pool and processes the given tasks.

        Args:
            tasks (List[Callable[..., Any]]): A list of coroutine functions to execute.
        """
        # Add tasks to the queue
        for task in tasks:
            await self.add_task(task)

        # Start workers
        workers = [asyncio.create_task(self.worker()) for _ in range(self.num_workers)]

        # Wait for all tasks to be processed
        await self.queue.join()

        # Cancel workers
        for worker in workers:
            worker.cancel()

        # Wait for workers to exit
        await asyncio.gather(*workers, return_exceptions=True)