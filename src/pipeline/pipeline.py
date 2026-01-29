from typing import Callable, List, Any

class Pipeline:
    """
    A processing pipeline that executes a series of steps in sequence.
    """

    def __init__(self):
        self.steps: List[Callable[..., Any]] = []

    def add_step(self, step: Callable[..., Any]) -> None:
        """
        Adds a processing step to the pipeline.

        Args:
            step (Callable[..., Any]): A callable representing a processing step.
        """
        self.steps.append(step)

    def execute(self, data: Any) -> Any:
        """
        Executes the pipeline on the given data.

        Args:
            data (Any): The input data to process.

        Returns:
            Any: The processed data after all steps.
        """
        for step in self.steps:
            try:
                data = step(data)
            except Exception as e:
                print(f"Step failed with error: {e}")
                break
        return data