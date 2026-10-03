# Module 2 requirement traceability

This map supplements the unchanged [frozen source](SOURCE_REQUIREMENTS.md) and
[architecture](ARCHITECTURE.md). Their original `Pending` markers remain frozen;
this artifact is the completion ledger. Story 10 requires human acceptance.

Audit baseline: clean `feature/module-02` at
`c7d7f2736a4bb6475aa329173ab2b12d83027098`. Stories 1–9 are accepted.
The documentation deliverables complete the evidence package for review.

Implementation links below point into the accepted core package. Verification
links name concrete test functions; parameterized cases are included in the
full-suite results recorded in [VERIFICATION.md](VERIFICATION.md).

| ID | Frozen requirement meaning | Implementation evidence | Verification evidence | Status |
| --- | --- | --- | --- | --- |
| M2-PE-01 | Demonstrate prompt anatomy | [construction.py](../src/prompt_engineering_systems/prompts/construction.py): `build_prompt` components; Structured UI | [test_prompt_construction.py](../tests/test_prompt_construction.py)::test_anatomy_zero_shot_and_structural_roles | Implemented / verified |
| M2-PE-02 | Demonstrate instruction hierarchy | [construction.py](../src/prompt_engineering_systems/prompts/construction.py): structural system/user roles; Structured UI | [test_prompt_construction.py](../tests/test_prompt_construction.py)::test_literal_content_never_forges_privileged_components | Implemented / verified |
| M2-PE-03 | Demonstrate context engineering | [context.py](../src/prompt_engineering_systems/prompts/context.py): `select_context`, provenance, whole-record character budget; prompt CLI | [test_prompt_context.py](../tests/test_prompt_context.py)::test_whole_record_skip_then_fit_and_exact_unicode_boundary | Implemented / verified |
| M2-PE-04 | Demonstrate role prompting | [templates.py](../src/prompt_engineering_systems/prompts/templates.py): `role_framing`; Teacher/Reviewer UI | [test_prompt_construction.py](../tests/test_prompt_construction.py)::test_role_comparison_preserves_application_policy | Implemented / verified |
| M2-PE-05 | Demonstrate few-shot prompting | [construction.py](../src/prompt_engineering_systems/prompts/construction.py): `FewShotExample`; authored-example UI checkbox | [test_prompt_construction.py](../tests/test_prompt_construction.py)::test_examples_preserve_pair_order_identity_and_provenance | Implemented / verified |
| M2-PE-06 | Demonstrate chain-of-thought prompting concepts | [techniques.py](../src/prompt_engineering_systems/prompts/techniques.py): `TechniqueSession.decompose`, bounded plan/summaries/synthesis; Advanced UI | [test_prompt_techniques.py](../tests/test_prompt_techniques.py)::test_decomposition_executes_plan_subproblems_and_synthesis | Implemented / verified |
| M2-PE-07 | Demonstrate tree-of-thought prompting concepts | [techniques.py](../src/prompt_engineering_systems/prompts/techniques.py): `tree`, candidate expansion/scoring/pruning; Advanced UI | [test_prompt_techniques.py](../tests/test_prompt_techniques.py)::test_tree_ranks_prunes_and_preserves_deterministic_ties | Implemented / verified |
| M2-PE-08 | Demonstrate self-consistency prompting | [techniques.py](../src/prompt_engineering_systems/prompts/techniques.py): `self_consistency`, normalized voting; Advanced UI | [test_prompt_techniques.py](../tests/test_prompt_techniques.py)::test_consistency_normalizes_votes_and_reports_agreement | Implemented / verified |
| M2-PE-09 | Demonstrate ReAct prompting | [techniques.py](../src/prompt_engineering_systems/prompts/techniques.py): `react`, validated proposals/authorized observations; Advanced UI | [test_prompt_techniques.py](../tests/test_prompt_techniques.py)::test_react_authorization_observations_and_completion | Implemented / verified |
| M2-SO-01 | Enforce JSON schemas | [schemas.py](../src/prompt_engineering_systems/structured/schemas.py): `schema_for_model`, `validate_against_schema` | [test_schema_validation.py](../tests/test_schema_validation.py)::test_supported_schema_behavior | Implemented / verified |
| M2-SO-02 | Implement typed outputs | [models.py](../src/prompt_engineering_systems/structured/models.py): `StructuredAnswer`, `SourceReference` | [test_structured_models.py](../tests/test_structured_models.py)::test_typed_answer_contains_typed_sources | Implemented / verified |
| M2-SO-03 | Integrate Pydantic models and validation | [contracts.py](../src/prompt_engineering_systems/contracts.py): `StrictContract`; strict typed validation | [test_output_validation.py](../tests/test_output_validation.py)::test_permissive_schema_cannot_bypass_typed_contract | Implemented / verified |
| M2-SO-04 | Validate model outputs | [validation.py](../src/prompt_engineering_systems/structured/validation.py): parsing, schema, strict fields/invariants | [test_output_validation.py](../tests/test_output_validation.py)::test_generated_schema_rejects_invalid_answer_fields; test_non_strict_json_is_rejected | Implemented / verified |
| M2-SA-01 | Implement or demonstrate prompt-injection defense | [construction.py](../src/prompt_engineering_systems/prompts/construction.py): role separation; independent tool policy | [test_red_team.py](../tests/test_red_team.py)::test_payloads_never_become_system_policy; test_detector_miss_does_not_grant_authority | Implemented / verified |
| M2-SA-02 | Implement or demonstrate jailbreak detection | [detection.py](../src/prompt_engineering_systems/safety/detection.py): `detect_indicators`, bounded phrase catalog | [test_safety_detection.py](../tests/test_safety_detection.py)::test_adversarial_and_control_indicators | Implemented / verified |
| M2-SA-03 | Establish safety boundaries | [tools.py](../src/prompt_engineering_systems/safety/tools.py): `ToolSession`; immutable application-owned `SafetyPolicy` | [test_safety_tools.py](../tests/test_safety_tools.py)::test_detector_miss_does_not_authorize_unknown_or_disallowed_tools; test_deny_default_and_execution_budget_exhaustion | Implemented / verified |
| M2-SA-04 | Perform red-team testing | [simulation.py](../src/prompt_engineering_systems/safety/simulation.py): `attack_cases`, `AttackSimulator`, `compare_attacks` | [test_red_team.py](../tests/test_red_team.py)::test_attack_classes_and_controls; test_simulation_repeatability_export_and_fixture_roundtrip | Implemented / verified |
| M2-LAB-01 | Structured output generator | [workflows.py](../src/prompt_engineering_systems/workflows.py): `generate_structured`; Structured UI | [test_generation_workflows.py](../tests/test_generation_workflows.py)::test_offline_is_deterministic_typed_and_network_free; [test_streamlit.py](../tests/test_streamlit.py)::test_invalid_output_rejected_with_safe_feedback | Implemented / verified |
| M2-LAB-02 | Schema validation | [workflows.py](../src/prompt_engineering_systems/workflows.py): `validate_schema_lab` | [test_generation_workflows.py](../tests/test_generation_workflows.py)::test_schema_lab_preserves_local_references_and_network_rejection | Implemented / verified |
| M2-LAB-03 | Evaluation workflows | [runner.py](../src/prompt_engineering_systems/evaluation/runner.py): `run_evaluation`, `StructuredFixtureExecutor`; metrics/export | [test_evaluation.py](../tests/test_evaluation.py)::test_versioned_case_loading_and_normal_failures | Implemented / verified |
| M2-LAB-04 | Prompt-injection attack simulation | [simulation.py](../src/prompt_engineering_systems/safety/simulation.py): seven safe synthetic attack/control pairs | [test_red_team.py](../tests/test_red_team.py)::test_local_paths_do_not_contact_network_or_execute_commands | Implemented / verified |
| M2-TOOL-01 | Pydantic | [contracts.py](../src/prompt_engineering_systems/contracts.py): runtime `BaseModel`, strict configuration/nested models | [test_structured_models.py](../tests/test_structured_models.py)::test_invalid_typed_answers_are_rejected | Implemented / verified |
| M2-TOOL-02 | OpenAI JSON Mode | [openai_json_mode.py](../src/prompt_engineering_systems/integrations/openai_json_mode.py): actual Chat Completions `json_object` request; injected SDK client | [test_openai_json_mode.py](../tests/test_openai_json_mode.py)::test_exact_json_mode_shape_roles_and_safe_output; test_mocked_adapter_workflow_still_requires_local_schema | Implemented / verified |
| M2-TOOL-03 | LangChain PromptTemplate | [langchain_templates.py](../src/prompt_engineering_systems/integrations/langchain_templates.py): real `PromptTemplate.from_template`/`format` | [test_langchain_templates.py](../tests/test_langchain_templates.py)::test_real_template_required_variables_and_literal_json_braces | Implemented / verified |
| M2-TOOL-04 | PromptLayer | [promptlayer.py](../src/prompt_engineering_systems/integrations/promptlayer.py): bounded REST logging/scores and separate receipts | [test_promptlayer.py](../tests/test_promptlayer.py)::test_logging_shape_sanitization_provenance_and_scores; test_http_failures_preserve_successful_evaluation | Implemented / verified |
| M2-DEL-01 | Structured prompting framework | [construction.py](../src/prompt_engineering_systems/prompts/construction.py), [CLI](../src/prompt_engineering_systems/prompts/__main__.py), [usage/trust documentation](../README.md) | [test_prompt_construction.py](../tests/test_prompt_construction.py)::test_offline_runnable_demonstration | Implemented / verified |
| M2-DEL-02 | Prompt evaluation pipeline | [runner.py](../src/prompt_engineering_systems/evaluation/runner.py), [evidence.py](../src/prompt_engineering_systems/evaluation/evidence.py), Evaluation UI/download and [documentation](../README.md) | [test_evaluation.py](../tests/test_evaluation.py)::test_export_excludes_raw_content_and_checks_integrity | Implemented / verified |
| M2-PORT-01 | Runnable Module 2 demonstration UI | [app.py](../app.py): four real-workflow areas; prior human browser review and accepted Story 9 | [test_streamlit.py](../tests/test_streamlit.py)::test_all_four_areas_are_reachable; test_startup_without_credentials_or_network | Implemented / verified |

## Evidence boundaries

- Prompt topics have runnable evidence through the UI or
  `uv run python -m prompt_engineering_systems.prompts`.
- Chain-of-thought concepts use explicit subproblems, concise summaries, and
  synthesis. Private chain-of-thought is not requested or exposed. Tree scoring
  is lexical; self-consistency agreement is vote share, not confidence.
- Injection defense combines structural instruction separation and independent
  authorization. Lexical detection can miss attacks or flag benign quotations.
- OpenAI and PromptLayer have real adapters and mocked verification. This story
  does not establish live service behavior or remote storage. Pydantic and
  LangChain execute locally.
- UI interaction/runtime evidence is AppTest. Prior manual browser review and
  Story 9 acceptance were supplied by the human reviewer; Story 10 does not
  claim a new browser or live-service check.
- Quality gates and source coverage are separate evidence dimensions.

## Mechanically checkable coverage

| Family | Mapped / authoritative |
| --- | --- |
| PE | 9 / 9 |
| SO | 4 / 4 |
| SA | 4 / 4 |
| LAB | 4 / 4 |
| TOOL | 4 / 4 |
| DEL | 2 / 2 |
| PORT | 1 / 1 |
| Total | 28 / 28 |

Run this PowerShell check from the repository root. Counts are derived from
the actual table rows and compared with the frozen source, including duplicates
and unknown IDs:

```powershell
@'
from collections import Counter
from pathlib import Path
import re
source = Path("module-02/docs/SOURCE_REQUIREMENTS.md").read_text(encoding="utf-8")
trace = Path("module-02/docs/TRACEABILITY.md").read_text(encoding="utf-8")
pattern = r"^\| (M2-[A-Z]+-\d{2}) \|"
authoritative = re.findall(pattern, source, re.M)
mapped = re.findall(pattern, trace, re.M)
assert len(authoritative) == len(set(authoritative))
assert Counter(mapped) == Counter(authoritative), "Missing, duplicate, or unknown IDs"
for family in sorted({identity.split("-")[1] for identity in authoritative}):
    expected = sum(identity.split("-")[1] == family for identity in authoritative)
    actual = sum(identity.split("-")[1] == family for identity in mapped)
    print(f"{family}: {actual}/{expected}")
print(f"Total: {len(mapped)}/{len(authoritative)}")
'@ | uv run python -
```
