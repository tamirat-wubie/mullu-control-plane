"""Calibration fixture: a NORMAL test file with exactly one test and no placeholder.

Used by the finding-verifier calibration corpus to confirm that a finding which
claims this file contains a forced-failure placeholder is rejected -- the claim's
evidence command counts zero such placeholders here, so the finding does not
reproduce. (This file deliberately avoids the literal forced-failure token so the
count is genuinely zero.)
"""


def test_config_loads():
    assert {"k": 1}["k"] == 1
