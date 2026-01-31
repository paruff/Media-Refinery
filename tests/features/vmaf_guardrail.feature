Feature: VMAF/PSNR Quality Guardrails
  Scenario: VMAF below threshold triggers retry
    Given a normalization plan with bitrate "1000"
    When the VMAF score is 85.0
    Then the plan should be marked as failed_quality_check
    And the bitrate should be bumped to "2000"

  Scenario: VMAF above threshold passes
    Given a normalization plan with bitrate "1000"
    When the VMAF score is 95.0
    Then the plan should not be marked as failed_quality_check
    And the bitrate should remain "1000"
