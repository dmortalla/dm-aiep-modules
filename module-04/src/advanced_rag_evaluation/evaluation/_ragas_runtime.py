"""Pinned RAGAS 0.3.1 SDK bridge, loaded only by explicit evaluation calls.

The application disables RAGAS usage tracking process-wide. Empty callback
managers prevent implicit tracing. Public single_turn_ascore performs real
RAGAS prompt generation, parsing, and metric computation. No default provider
factory, model download, or credential discovery is invoked by this bridge.
"""

import json
import math
import os
from copy import deepcopy

# Fixed application policy, never derived from evaluation data or judge output.
os.environ["RAGAS_DO_NOT_TRACK"] = "true"

import ragas  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402
from langchain_core.callbacks import CallbackManager  # noqa: E402
from langchain_core.outputs import Generation, LLMResult  # noqa: E402
from langchain_core.prompt_values import PromptValue  # noqa: E402
from ragas._analytics import do_not_track  # noqa: E402
from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.embeddings import BaseRagasEmbeddings  # noqa: E402
from ragas.llms import BaseRagasLLM  # noqa: E402
from ragas.metrics import (  # noqa: E402
    Faithfulness,
    LLMContextPrecisionWithReference,
    ResponseRelevancy,
)
from ragas.metrics._answer_relevance import ResponseRelevanceInput  # noqa: E402
from ragas.metrics._context_precision import QAC  # noqa: E402
from ragas.metrics._faithfulness import (  # noqa: E402
    NLIStatementInput,
    StatementGeneratorInput,
)
from ragas.run_config import RunConfig  # noqa: E402

from ..errors import (  # noqa: E402
    EvaluationError,
    EvaluationIntegrationError,
    EvaluationResultError,
)
from ..semantic_retrieval import (  # noqa: E402
    Embedder,
    EmbeddingBatch,
    validate_texts,
)
from .ragas_adapter import (  # noqa: E402
    METRIC_NAMES,
    EvaluationCase,
    EvaluationConfig,
    EvaluationResult,
    EvaluationScores,
    Judge,
    JudgeCall,
    RagasEvaluator,
    ReplayReply,
    _score,
    _text,
)

do_not_track.cache_clear()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys instead of silently overwriting evidence."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationResultError("Return JSON without duplicate keys.")
        result[key] = value
    return result


def _strict_schema(schema: dict) -> dict:
    """Strengthen only output validation; never change RAGAS metric algorithms."""
    result = deepcopy(schema)

    def tighten(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
            if node.get("type") == "string":
                node.update(minLength=1, maxLength=32768, pattern=r"\S")
            for key, child in tuple(node.items()):
                if key in ("verdict", "noncommittal") and isinstance(child, dict):
                    child["enum"] = [0, 1]
                tighten(child)
        elif isinstance(node, list):
            for child in node:
                tighten(child)

    tighten(result)
    return result


def _validated_completion(prompt: str, completion: str) -> None:
    """Validate strict raw JSON before RAGAS can coerce or log malformed output."""
    if type(completion) is not str:
        raise EvaluationResultError("Return a JSON string from the configured judge.")
    try:
        if len(completion.encode("utf-8")) > 131_072:
            raise EvaluationResultError("Limit judge output to 131072 UTF-8 bytes.")
        # The first schema and fixed input marker belong to the pinned SDK's
        # prompt template. Untrusted strings inside JSON cannot add raw markers.
        schema_text = prompt.split(
            "following schema as specified in JSON Schema:\n", 1
        )[1]
        schema, _ = json.JSONDecoder().raw_decode(schema_text)
        input_text = prompt.split(
            "\nNow perform the same with the following input\ninput: ", 1
        )[1]
        request, _ = json.JSONDecoder().raw_decode(input_text)
        output = json.loads(completion, object_pairs_hook=_unique_object)
        Draft202012Validator(_strict_schema(schema)).validate(output)
        if set(request) == {"context", "statements"}:
            if [item["statement"] for item in output["statements"]] != request[
                "statements"
            ]:
                raise EvaluationResultError("Retain every judged statement in order.")
    except EvaluationError:
        raise
    except Exception as exc:
        raise EvaluationResultError(
            "Return strict JSON matching the RAGAS judge schema."
        ) from exc


class _JudgeBridge(BaseRagasLLM):
    """Convert an injected Judge to real RAGAS LLM generations with raw evidence."""

    def __init__(self, judge: Judge) -> None:
        super().__init__(run_config=RunConfig(max_retries=1, max_wait=0))
        self.judge = judge
        self.metric = "faithfulness"
        self.calls: list[JudgeCall] = []

    def is_finished(self, response: LLMResult) -> bool:
        """Structured injected responses represent completed model calls."""
        return True

    def generate_text(
        self,
        prompt: PromptValue,
        n: int = 1,
        temperature: float = 1e-8,
        stop: list[str] | None = None,
        callbacks: object = None,
    ) -> LLMResult:
        """Reject synchronous invocation; this adapter uses asynchronous RAGAS."""
        raise EvaluationIntegrationError("Use the asynchronous evaluation boundary.")

    async def agenerate_text(
        self,
        prompt: PromptValue,
        n: int = 1,
        temperature: float | None = None,
        stop: list[str] | None = None,
        callbacks: object = None,
    ) -> LLMResult:
        """Invoke the selected judge once; preserve and strictly validate its output."""
        if n != 1:
            raise EvaluationIntegrationError("Use one completion per RAGAS prompt.")
        text = prompt.to_string()
        _text(text, "RAGAS prompt", 1_048_576)
        try:
            completion = await self.judge.complete(text)
        except EvaluationError:
            raise
        except Exception as exc:
            raise EvaluationIntegrationError(
                "Check the configured evaluation judge."
            ) from exc
        _validated_completion(text, completion)
        self.calls.append(JudgeCall(self.metric, text, completion))
        return LLMResult(generations=[[Generation(text=completion)]])


class _EmbeddingBridge(BaseRagasEmbeddings):
    """Bridge Module 4's ordered EmbeddingBatch contract into RAGAS."""

    def __init__(self, embedder: Embedder) -> None:
        super().__init__()
        self.embedder = embedder
        self.set_run_config(RunConfig(max_retries=1, max_wait=0))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Validate ordered finite nonzero model vectors before RAGAS cosine scoring."""
        try:
            validate_texts(tuple(texts))
            batch = self.embedder.embed(tuple(texts))
        except Exception as exc:
            raise EvaluationIntegrationError(
                "Check the configured evaluation embedding model."
            ) from exc
        if (
            type(batch) is not EmbeddingBatch
            or len(batch.vectors) != len(texts)
            or batch.dimension != self.embedder.dimension
            or any(math.hypot(*vector) == 0 for vector in batch.vectors)
        ):
            raise EvaluationResultError("Return ordered nonzero evaluation embeddings.")
        return [list(vector) for vector in batch.vectors]

    def embed_query(self, text: str) -> list[float]:
        """Return the single question vector through the same validated boundary."""
        return self.embed_documents([text])[0]

    async def aembed_query(self, text: str) -> list[float]:
        """Expose the asynchronous RAGAS embedding interface."""
        return self.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Expose the asynchronous RAGAS batch interface."""
        return self.embed_documents(texts)


async def score_case(
    evaluator: RagasEvaluator, case: EvaluationCase, config: EvaluationConfig
) -> EvaluationResult:
    """Execute public RAGAS metric calls without default clients or callbacks."""
    llm = _JudgeBridge(evaluator.judge)
    embeddings = _EmbeddingBridge(evaluator.embedder)
    sample = SingleTurnSample(
        user_input=case.question,
        response=case.response,
        reference=case.reference,
        retrieved_contexts=[chunk.content for chunk in case.contexts],
    )
    metrics = (
        Faithfulness(llm=llm),
        LLMContextPrecisionWithReference(llm=llm),
        ResponseRelevancy(llm=llm, embeddings=embeddings, strictness=config.strictness),
    )
    scores = []
    for name, metric in zip(METRIC_NAMES, metrics, strict=True):
        llm.metric = name
        try:
            score = await metric.single_turn_ascore(
                sample,
                callbacks=CallbackManager(handlers=[], inheritable_handlers=[]),
                timeout=config.timeout_seconds,
            )
        except EvaluationError:
            raise
        except Exception as exc:
            raise EvaluationIntegrationError(
                f"Check the RAGAS {name} model boundary and timeout."
            ) from exc
        # numpy scalar results are expected from RAGAS; accept real numeric
        # scalars, but never strings/bools/containers masquerading as scores.
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise EvaluationResultError(f"Require a numeric RAGAS {name} score.")
        _score(float(score), name)
        scores.append(float(score))
    return EvaluationResult(
        case,
        EvaluationScores(*scores),
        config,
        evaluator.evidence_kind,
        evaluator.judge_id,
        evaluator.embedding_id,
        ragas.__version__,
        tuple(llm.calls),
    )


def replay_replies(
    case: EvaluationCase,
    statements: tuple[str, ...],
    statement_verdicts: tuple[int, ...],
    context_verdicts: tuple[int, ...],
    generated_question: str,
    noncommittal: int,
) -> tuple[ReplayReply, ...]:
    """Construct exact SDK prompts and fixed completions; compute no metric scores."""
    faithfulness = Faithfulness()
    precision = LLMContextPrecisionWithReference()
    relevance = ResponseRelevancy()
    replies = [
        ReplayReply(
            faithfulness.statement_generator_prompt.to_string(
                StatementGeneratorInput(question=case.question, answer=case.response)
            ),
            json.dumps({"statements": list(statements)}),
        ),
        ReplayReply(
            faithfulness.nli_statements_prompt.to_string(
                NLIStatementInput(
                    context="\n".join(chunk.content for chunk in case.contexts),
                    statements=list(statements),
                )
            ),
            json.dumps(
                {
                    "statements": [
                        {
                            "statement": text,
                            "reason": "Fixed offline fixture judgment.",
                            "verdict": verdict,
                        }
                        for text, verdict in zip(
                            statements, statement_verdicts, strict=True
                        )
                    ]
                }
            ),
        ),
    ]
    for chunk, verdict in zip(case.contexts, context_verdicts, strict=True):
        replies.append(
            ReplayReply(
                precision.context_precision_prompt.to_string(
                    QAC(
                        question=case.question,
                        context=chunk.content,
                        answer=case.reference,
                    )
                ),
                json.dumps(
                    {
                        "reason": "Fixed offline fixture judgment.",
                        "verdict": verdict,
                    }
                ),
            )
        )
    replies.append(
        ReplayReply(
            relevance.question_generation.to_string(
                ResponseRelevanceInput(
                    response=case.response,
                )
            ),
            json.dumps({"question": generated_question, "noncommittal": noncommittal}),
        )
    )
    return tuple(replies)
