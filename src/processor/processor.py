from typing import Any, Callable, List


class Processor:
    """
    A generic processor that applies a series of processing functions to data.
    """

    def __init__(self):
        self.functions: List[Callable[[Any], Any]] = []

    def add_function(self, func: Callable[[Any], Any]) -> None:
        """
        Adds a processing function to the processor.

        Args:
            func (Callable[[Any], Any]): A function that takes data as input and returns processed data.
        """
        self.functions.append(func)

    def process(self, data: Any) -> Any:
        """
        Processes the data through all added functions in sequence.

        Args:
            data (Any): The input data to process.

        Returns:
            Any: The processed data after all functions have been applied.
        """
        for func in self.functions:
            try:
                data = func(data)
            except Exception as e:
                print(f"Processing function failed with error: {e}")
                break
        return data
