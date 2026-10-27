"""Named NORMAL real-local budget profile (ADR-008); authority-free data.

This module is policy configuration, never execution authority. It holds one
named, immutable ``LiveBudget`` instance that records the human-approved
NORMAL execution-envelope values for the canonical real-local Ollama
Researcher -> Analyst -> Critic workflow on the accepted host/model profile
(see ``docs/adr/008-real-local-canonical-budget-profile.md``).

The profile is evidence-class budget data only:

- it contains no ``ModelSelection`` and never states a provider or model;
- it never instantiates, returns or wraps ``LiveAuthorization``;
- there is no helper or factory that turns the profile into authority;
- importing this module causes no provider, model, network, credential or
  file side effects;
- real canonical execution still requires a fresh, separately constructed
  explicit ``LiveAuthorization`` at the call site (see ``canonical_workflow``),
  with every budget value stated by the human-conscious caller.

Deviation from the NORMAL values is permitted only through that separate
explicit authority path with fresh human authorization; nothing in this module
invalidates or substitutes it. The generic ``MAX_DEADLINE_MS`` schema ceiling
in ``live_contracts`` remains unchanged, non-NORMAL, and never a default: this
profile is one named configuration, not a schema or runtime default. This
policy governs only the canonical real-local workflow. It does not govern the
synthetic reviewer console (whose own accepted authority stays 30,000 ms /
5,000 ms), arbitrary future live modes, or hosted providers generally.

NORMAL values (all human-approved; no derivation authority is implied here):

- ``deadline_ms`` / ``call_timeout_ms``: 200,000 / 45,000, structurally
  covering four sequential calls at the full per-call bound plus a fixed
  acceptance/reap allowance: ``4 * 45,000 + 20,000 == 200,000``.
- planned calls 3; ``max_model_calls`` 4 so the single ``max_repair_attempts``
  repair stays inside the total; transport retries 0; concurrency 1.
- content/resource bounds at the accepted real-local contract ceilings,
  unchanged: task text 4,096 characters, provider output limit 4,096 tokens
  (``num_predict``), reply bound 16,000 bytes. With the provider output limit
  at the contract ceiling, a verbose but schema-valid reply completes
  generation and is judged by the accepted parse/validation taxonomy
  (repairable ``malformed_output`` when malformed) instead of being forced
  prematurely into the non-repairable provider-length classification; only a
  genuine overshoot of 4,096 tokens or 16,000 bytes remains closed as
  ``output_too_large``.

Uncertainty scope: the values derive from two real workflow runs and only one
with per-segment timing, so they are not a percentile, SLA or statistical
generalization. They are scoped to this host/model profile and require
recalibration when host, provider version or model changes.
"""

from .live_contracts import LiveBudget

__all__ = [
    "NORMAL_REAL_LOCAL_ALLOWANCE_MS",
    "NORMAL_REAL_LOCAL_BUDGET",
    "NORMAL_REAL_LOCAL_CALL_TIMEOUT_MS",
    "NORMAL_REAL_LOCAL_DEADLINE_MS",
    "NORMAL_REAL_LOCAL_MAX_MODEL_CALLS",
]

NORMAL_REAL_LOCAL_CALL_TIMEOUT_MS = 45_000
NORMAL_REAL_LOCAL_DEADLINE_MS = 200_000
# Fixed workflow-level time not attributable to the four sequential call
# bounds: result acceptance, validation and bounded cleanup/reap handling.
NORMAL_REAL_LOCAL_ALLOWANCE_MS = 20_000
NORMAL_REAL_LOCAL_MAX_MODEL_CALLS = 4

NORMAL_REAL_LOCAL_BUDGET = LiveBudget(
    max_model_calls=4,
    max_repair_attempts=1,
    max_concurrency=1,
    deadline_ms=200_000,
    call_timeout_ms=45_000,
    max_input_chars=4_096,
    max_output_tokens=4_096,
    max_reply_bytes=16_000,
)
