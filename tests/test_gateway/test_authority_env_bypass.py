"""Authority dev/test bypass must require an explicit MULLU_ENV.

Regression test for the fail-open default: an unset/blank MULLU_ENV previously
defaulted to ``local_dev``, which granted the approval-webhook,
authority-operator, and deployment-authority routes their secret-skipping
bypass with no secret configured. A forgotten env var in production opened
every authority route. The bypass must now require an EXPLICIT dev/test env.
"""

from gateway.server import _explicit_dev_or_test_env


def test_explicit_dev_and_test_envs_grant_bypass():
    assert _explicit_dev_or_test_env("local_dev") is True
    assert _explicit_dev_or_test_env("test") is True
    assert _explicit_dev_or_test_env("LOCAL_DEV") is True  # case-insensitive
    assert _explicit_dev_or_test_env("  test  ") is True  # whitespace-tolerant


def test_production_like_envs_never_bypass():
    assert _explicit_dev_or_test_env("production") is False
    assert _explicit_dev_or_test_env("prod") is False
    assert _explicit_dev_or_test_env("pilot") is False
    assert _explicit_dev_or_test_env("staging") is False


def test_unset_or_blank_env_fails_closed():
    # The security fix: an unset/blank MULLU_ENV must NOT grant the bypass.
    assert _explicit_dev_or_test_env("") is False
    assert _explicit_dev_or_test_env("   ") is False
    # Unknown/typo'd values also fail closed rather than defaulting open.
    assert _explicit_dev_or_test_env("locel_dev") is False
    assert _explicit_dev_or_test_env("dev") is False
