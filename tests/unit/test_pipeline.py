import pytest
from src.pipeline.pipeline import Pipeline

def test_pipeline():
    pipeline = Pipeline()

    def step1(data):
        return data + 1

    def step2(data):
        return data * 2

    pipeline.add_step(step1)
    pipeline.add_step(step2)

    result = pipeline.execute(3)

    assert result == 8