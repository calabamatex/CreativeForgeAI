"""Proves the ``paid`` cost-gate works (P6-T1).

This file contains a single, trivial ``@pytest.mark.paid`` test whose only job
is to demonstrate the gating MECHANISM end to end:

  * Under a bare ``pytest`` run (and the PR-CI gate) it is SKIPPED with the
    message "paid test — set RUN_PAID_TESTS=1 to run" (see the
    ``pytest_collection_modifyitems`` hook in ``tests/conftest.py``). No paid
    provider call is ever made by default.
  * Under ``RUN_PAID_TESTS=1 pytest -m paid`` it actually RUNS and passes.

It asserts something trivial on purpose — there is NO real paid provider call
here. When real paid tests land (e.g. P2-T1's deferred Firefly live test), they
just add ``@pytest.mark.paid`` and inherit this exact safe-by-default gating.

The full backend x locale x ratio worst-case matrix (~45 paid calls) must use
``@pytest.mark.paid_matrix`` instead, which is double-gated behind BOTH
``RUN_PAID_TESTS=1`` and ``RUN_FULL_MATRIX=1`` so it can never reach the default
or PR-CI path. (No such matrix test exists on this branch yet; the convention is
documented in ``tests/conftest.py``.)
"""
import os

import pytest


@pytest.mark.paid
def test_paid_gate_runs_only_when_opted_in():
    """Trivial paid-tier test: skipped by default, runs under RUN_PAID_TESTS=1.

    If this body executes at all, the gate let us in — which only happens when
    ``RUN_PAID_TESTS=1``. Assert that invariant plus a trivial truth so the test
    is meaningful but costs nothing.
    """
    assert os.getenv("RUN_PAID_TESTS") == "1", (
        "paid test executed without RUN_PAID_TESTS=1 — the cost gate is broken"
    )
    assert 1 + 1 == 2
