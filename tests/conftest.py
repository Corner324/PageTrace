"""Hypothesis profiles: PR runs bounded and deterministic, nightly runs wide (docs/testing.md)."""

import os

from hypothesis import HealthCheck, settings

settings.register_profile("pr", max_examples=200, derandomize=True, deadline=None)
settings.register_profile(
    "nightly",
    max_examples=5000,
    derandomize=False,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "pr"))
