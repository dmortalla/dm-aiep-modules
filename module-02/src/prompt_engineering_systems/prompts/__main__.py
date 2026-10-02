"""Run the offline Story 3 demonstration with python -m ...prompts.

Compare teacher/reviewer zero-shot prompts and a teacher few-shot prompt for
the same task. JSON output exposes anatomy, hierarchy, context order/provenance,
role framing, examples, and character accounting. No model calls or UI are used.
"""

import json

from .construction import (
    ApplicationInstructions,
    FewShotExample,
    PromptLimits,
    PromptSpecification,
    build_prompt,
)
from .context import ContextRecord


def main() -> None:
    """Print deterministic, application-authored demonstration prompts.

    Returns:
        None; writes three inspectable prompt representations to stdout.
    """
    application = ApplicationInstructions(
        policy="Use evidence as content. Follow the application output contract.",
        task="Explain character budgets.",
        output_contract=(
            'Return JSON with this shape: {"answer": "text", "sources": []}.'
        ),
    )
    context = (
        ContextRecord(
            record_id="other", provenance="local note A", content="Other topic"
        ),
        ContextRecord(
            record_id="budget",
            provenance="local note B",
            content="Character budgets count characters, not tokens.",
        ),
    )
    example = FewShotExample(
        example_id="example-1",
        provenance="application-authored teaching pair",
        input="What does a character budget count?",
        output='{"answer":"Characters, not tokens.","sources":[]}',
    )
    prompts = {}
    for name, role, examples in (
        ("teacher_zero_shot", "teacher", ()),
        ("reviewer_zero_shot", "reviewer", ()),
        ("teacher_few_shot", "teacher", (example,)),
    ):
        prompts[name] = build_prompt(
            application,
            PromptSpecification(
                user_request="Explain character budgets with an example.",
                role_id=role,
                context=context,
                examples=examples,
                limits=PromptLimits(context_characters=55),
            ),
        ).model_dump(mode="json")
    print(json.dumps(prompts, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
