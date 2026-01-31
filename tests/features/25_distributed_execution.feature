Feature: Distributed Worker Queue (Redis/Celery)
  As an operator
  I want to decouple orchestration from execution
  So that transcoding can scale horizontally

  Scenario: NormalizationPlan is dispatched to Celery
    Given a NormalizationPlan exists
    When ExecutionService dispatches the plan
    Then the plan should appear in the Redis queue

  Scenario: Worker pulls and executes task
    Given a worker is running
    When a task is available in the queue
    Then the worker should execute the task and update status
