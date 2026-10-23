# ADR-008: Real-Local Canonical Execution Budget Profile (NORMAL)

- Status: Accepted
- Decision authority: Explicit human approval of ADR-008 and the NORMAL profile values
- Recorded: 2026-10-22
- Scope: Named budget-profile data for the canonical real-local workflow; Architecture B+ runtime ownership, ADR-007 supervision, all accepted contracts and all 26 source requirement statuses remain untouched

## Context

The canonical real-local workflow has no default deadline, call timeout or
budget. Every `LiveBudget` value is explicit and operator/HITL supplied, and
`MAX_DEADLINE_MS = 300,000 ms` in `live_contracts.py` is a generic provisional
schema ceiling, not a canonical policy. The synthetic reviewer console runs a
separate accepted authority of 30,000 ms / 5,000 ms, but Run 2 — the first
successful real workflow execution — recorded no numeric budget, so the
practice had no reconstructable NORMAL reference. Before future real-local
runs, the normal envelope needs a defensible, recorded, evidence-derived
policy that remains strictly separate from execution authority.

## Accepted evidence and corrected derivation

Live timing observations:

| Observation | Value |
| --- | --- |
| Run 2 total workflow duration | ~49.8 s (3 calls, 0 repairs, no segments recorded) |
| Run 3 total workflow duration | 64,531 ms result / 65,125 ms terminal record |
| Run 3 Researcher segment | 38,622 ms, including child spawn outside `call_timeout_ms` |
| Run 3 in-scope call floor, corrected | ~37.6 s (spawn excluded) |
| Run 3 Analyst / Critic segments | ~12.3 s / ~14.1 s |
| Run 3 post-result acceptance and reap | ~0.6 s acceptance tail; ~0.09 s reap |
| Token-derived cross-run rate variability | ~23.6 tok/s (Run 2) vs ~18.0 tok/s (Run 3); aggregate difference ~31.6% |

Correction recorded: the 45,000 ms call bound therefore provides approximately
**19.6% headroom over the single observed in-scope per-call floor (37.6 s)**,
not over the raw segment that included process spawn. The aggregate cross-run
token-rate difference is approximately 31.6%, and 37.6 × 1.316 ≈ 49.5 s
exceeds 45,000 ms: the NORMAL call timeout therefore does **not** cover a
hypothetical future call slowed by the full observed cross-run rate
difference. It is a deliberately tight, least-authority bound calibrated above
the single observed in-scope cold-call floor, not a statistical reliability
guarantee. A sufficiently slower future cold call may time out; that failure
is fail-closed (`TIMED_OUT`), consumes that run's authorization, triggers no
automatic retry or rerun, and another attempt requires fresh HITL. These
observations are n = 2 real workflow runs and only n = 1 with per-segment
timing. No percentile, SLA, reliability percentile or statistical
generalization is claimed. The values are scoped to this host/model profile
(local Ollama with `qwen2.5-coder:7b` on the accepted workstation) and
require recalibration when host, provider version or model changes.

## Decision

The application records one named, immutable, human-approved **NORMAL** budget
profile as plain `LiveBudget` data in `live_policy.py`, instance
`NORMAL_REAL_LOCAL_BUDGET`. The name scopes this policy to the canonical
real-local workflow only; it does not govern the synthetic reviewer console,
arbitrary future live modes, or hosted providers generally:

| Field | NORMAL value |
| --- | --- |
| `deadline_ms` | 200,000 |
| `call_timeout_ms` | 45,000 |
| expected model calls | 3 (planned roles) |
| `max_model_calls` | 4 |
| `max_repair_attempts` | 1 |
| `max_concurrency` | 1 |
| transport retries | 0 |
| `max_input_chars` | 4,096 |
| `max_output_tokens` | 4,096 |
| `max_reply_bytes` | 16,000 |

The content/resource rows are the accepted real-local contract ceilings
(`MAX_INPUT_CHARS`, `MAX_OUTPUT_TOKENS`, `MAX_REPLY_BYTES`), unchanged;
they are not the synthetic console's own 4,096 / 256-token / 4,096-byte
envelope, and the two envelopes stay uncoupled. With the provider output
limit restored to the contract ceiling, a verbose but schema-valid reply
completes generation and is judged by the accepted parse/validation taxonomy
(repairable `malformed_output` when malformed) instead of being forced
prematurely into the non-repairable provider-length `output_too_large`
classification; only a genuine overshoot of 4,096 tokens or 16,000 bytes
remains closed.

Derivation. Calls are strictly sequential (concurrency 1) and the naive maximum
is `max_model_calls × call_timeout_ms`. For the stated per-call bound to be the
operative bound for every call — including the optional repair — the deadline
must cover four full call bounds plus workflow-level time that is not
attributable to the four calls: result acceptance/validation and bounded
cleanup/reap handling. Hence 4 × 45,000 + 20,000 = 200,000, where the 20,000 ms
allowance covers the measured ~0.6–1.6 s per-workflow acceptance/reap tails
and bounded supervisor reserves plus an explicit operator element. The
45,000 ms call value is sized in the corrected-derivation section above:
approximately 19.6% over the ~37.6 s in-scope floor, a deliberately tight
least-authority trade-off that does not extend to the full ~31.6% observed
cross-run rate difference (see that section for the honest timeout trade-off).

If `deadline_ms` were below `4 × call_timeout_ms`, late calls would be cut
by the run deadline instead of the stated call timeout: the policy would stop
matching the operative constraint, and the repair path would be only
conditionally reachable. Sizing the deadline at the structural maximum with a
fixed allowance keeps policy and operative behavior coincident, while still
failing closed first if a call or the run stalls.

## Alternatives considered

- Tighter envelopes (60/20, 90/30 or 120/30 seconds): all make the observed
  38.6 s Researcher segment falsely time out; incompatible with the strongest
  single in-scope call observation.
- 120,000 / 45,000: call bound compatible, but 4 × 45,000 > 120,000, so the
  run deadline would cut late calls and the repair path is not guaranteed the
  full stated bound; policy and operative behavior diverge.
- Default `LiveAuthorization` or an authorization factory: rejected. Policy
  configuration and execution authority must remain separate; no zero-argument
  path to authority is created.
- Raising or removing `MAX_DEADLINE_MS`: rejected; 200,000 fits the existing
  generic 300,000 ceiling and no evidence supports changing it.

## Profile versus authority

The NORMAL profile (`NORMAL_REAL_LOCAL_BUDGET`) is a named immutable
`LiveBudget` instance only. It
contains no `ModelSelection`, no provider or model identity, and never
instantiates, returns or wraps a `LiveAuthorization`. There is no helper that
turns the profile into authority. Every real live execution still requires
fresh explicit human authorization and explicit `LiveAuthorization`
construction at the call site. The canonical service and console paths do not
import or consume the profile.

## Unchanged boundaries

- `MAX_DEADLINE_MS` remains 300,000 ms: a provisional generic schema ceiling,
  not a default and not the NORMAL authorization. Its "provisional until a
  separately authorized measurement" note is unchanged.
- Synthetic reviewer-console authority remains 30,000 ms / 5,000 ms and stays
  independent of real-local policy; the path's deterministic synthetic
  transport has no model-load or token-rate variability to cover, and the two
  envelopes must not be coupled.
- Timeout remains fail-closed (`TIMED_OUT` consumes the run). A timed-out run
  never triggers automatic retry, rerun, repair or provider substitution;
  another attempt always needs fresh HITL and consumes fresh authorization.
- Run 3 remains valid factual real-local technical evidence and is classified
  permanently as an **out-of-policy observation**. The supplied runtime pair
  300,000/120,000 ms was schema-valid and the run completed within it;
  however, human authorization of exactly those values before Run 3 is **not
  established** by accepted evidence, so the human-authorization match is
  **unverified**. Runtime budget compliance is never proof of human
  authorization. Run 3 is not retroactively authorized, is not an authorized
  live success, and is outside NORMAL because 300,000 > 200,000 and
  120,000 > 45,000; its calibration measurements informed these values.

## Deviation policy

Any envelope other than NORMAL requires fresh explicit HITL for that deviation
and explicit `LiveAuthorization` construction with every budget value stated.
A deviation does not change the evidence class (real-local stays real-local),
but it does change the acceptance path: deviation evidence may be recorded as
real-local results and is not automatically covered by acceptance of the
NORMAL profile review.

## Evidence-ledger requirements

Each future real-local run's evidence record must represent, separately and
with nothing left to reconstruction:

1. **Runtime/schema validity** of the supplied budget pair (schema-valid or
   refused).
2. **Execution consistency**: whether the run completed within the actually
   supplied runtime values, with actual total duration, calls, repairs,
   retries, token accounting, cleanup/reaped state and per-segment role
   timing where observable.
3. **Human-authorized budget**: the complete `LiveBudget` the human authorized,
   with the HITL authorization reference/date; if the authorized values cannot
   be established, the record says so instead of inferring them.
4. **Actually-used budget**: the complete `LiveBudget` the runtime enforced
   (identical to the supplied one; recorded explicitly).
5. **Human-authorization match**: a `within_human_authorization` verdict —
   `true`, `false`, or `unverified` — with the reason when negative or
   unverified. Runtime budget compliance is never substituted for this
   verdict, and the field name deliberately differs from the runtime evidence
   validation that a supplied budget encloses the execution (that runtime
   check keeps its own accepted name and semantics).
6. **Policy classification**: `authorized_live_success`,
   `out_of_policy_observation`, or a NORMAL-deviation label when applicable.

Recording belongs to the documentation/evidence ledger (e.g.,
`CANONICAL_LIVE_WORKFLOW.md`), not the runtime schema: the accepted live
contracts are frozen evidence planes, and HITL references, version strings
and ledger classifications are authority/documentation metadata, not
runtime-produced data. Runtime/provider version, model identifier and local
projection statuses round out the record. Sensitive recording stays excluded:
no prompts, raw replies, credentials, provider diagnostics or payloads.

## Consequences and future recalibration

The profile removes Run 2's numeric ambiguity for every future authorized
run and gives false-timeout and bounded-exposure trade-offs an explicit,
reviewable place. These values bound nothing about model quality or
semantic correctness. The profile must be recalibrated when the host profile,
Ollama version, model or operating conditions change materially; a separately
authorized measurement campaign (multiple runs, documented budgets) is the
only evidence class that could later move the generic ceiling or the NORMAL
values. Approval of ADR-008 authorizes no live execution.
