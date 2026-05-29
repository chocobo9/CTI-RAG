from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from rag_cti._logging import get_logger
from rag_cti.types import GeneratedAnswer

logger = get_logger(__name__)


@dataclass(frozen=True)
class RagasEvalResult:
    n_queries: int
    faithfulness: float
    answer_relevancy: float
    # context_precision/recall require a reference answer; default -1.0 = "not computed".
    context_precision: float = -1.0
    context_recall: float = -1.0
    per_query: list[dict] = field(default_factory=list)
    config: str = ""
    timestamp: str = ""


def answers_to_ragas_dataset(
    answers: list[GeneratedAnswer],
    references: list[str] | None = None,
) -> list[dict]:
    """Convert GeneratedAnswer list to RAGAS SingleTurnSample-compatible dicts.

    Returns dicts with keys: user_input, retrieved_contexts, response, and
    (when `references` is given) reference — the ground-truth answer needed by
    context_precision / context_recall.
    """
    if references is not None and len(references) != len(answers):
        raise ValueError(
            f"references ({len(references)}) must align with answers ({len(answers)})"
        )
    samples = []
    for i, a in enumerate(answers):
        contexts = [r.document.content for r in a.query_result.results]
        sample = {
            "user_input": a.query,
            "retrieved_contexts": contexts,
            "response": a.answer,
        }
        if references is not None:
            sample["reference"] = references[i]
        samples.append(sample)
    return samples


def _build_judge_llm(settings: object) -> object:
    deepseek_key = getattr(settings, "deepseek_api_key", None)
    if deepseek_key is not None:
        key_value = deepseek_key.get_secret_value() if hasattr(deepseek_key, "get_secret_value") else str(deepseek_key)
    else:
        key_value = ""

    if not key_value:
        raise ValueError(
            "RAGAS evaluation requires DEEPSEEK_API_KEY to be set in .env"
        )

    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    chat = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=key_value,
        openai_api_base="https://api.deepseek.com/v1",
    )
    return LangchainLLMWrapper(chat)


def _build_embeddings() -> object:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    hf = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
    return LangchainEmbeddingsWrapper(hf)


def run_ragas_eval(
    answers: list[GeneratedAnswer],
    config: str = "",
    settings: object | None = None,
    references: list[str] | None = None,
) -> RagasEvalResult:
    """Run RAGAS metrics on GeneratedAnswers.

    Always computes faithfulness + answer_relevancy. When `references` (the
    ground-truth reference answers) are provided, ALSO computes context_precision
    and context_recall (SPEC §D.1). Without references those stay at -1.0.
    """
    if settings is None:
        from rag_cti.config import get_settings
        settings = get_settings()

    sample_dicts = answers_to_ragas_dataset(answers, references=references)
    if not sample_dicts:
        return RagasEvalResult(
            n_queries=0,
            faithfulness=0.0,
            answer_relevancy=0.0,
            config=config,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.metrics import AnswerRelevancy, Faithfulness

    llm = _build_judge_llm(settings)
    embeddings = _build_embeddings()

    use_context = references is not None and any(r for r in references)

    samples = [
        SingleTurnSample(
            user_input=s["user_input"],
            retrieved_contexts=s["retrieved_contexts"],
            response=s["response"],
            reference=s.get("reference"),
        )
        for s in sample_dicts
    ]
    dataset = EvaluationDataset(samples=samples)

    metrics = [Faithfulness(llm=llm), AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=1)]
    if use_context:
        from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall
        metrics += [LLMContextPrecisionWithReference(llm=llm), LLMContextRecall(llm=llm)]

    logger.info("running ragas eval", n_queries=len(samples), config=config, context=use_context)

    result = evaluate(dataset=dataset, metrics=metrics, show_progress=True)
    df = result.to_pandas()
    # df column for each metric is the metric's .name attribute.
    col = {type(m).__name__: m.name for m in metrics}
    cp_col = col.get("LLMContextPrecisionWithReference")
    cr_col = col.get("LLMContextRecall")

    per_query = []
    for i, row in df.iterrows():
        pq = {
            "question": sample_dicts[i]["user_input"],
            "faithfulness": float(row.get("faithfulness", 0.0)),
            "answer_relevancy": float(row.get("answer_relevancy", 0.0)),
        }
        if use_context:
            pq["context_precision"] = float(row.get(cp_col, 0.0))
            pq["context_recall"] = float(row.get(cr_col, 0.0))
        per_query.append(pq)

    def _avg(key: str) -> float:
        vals = [pq[key] for pq in per_query if key in pq]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    return RagasEvalResult(
        n_queries=len(samples),
        faithfulness=_avg("faithfulness"),
        answer_relevancy=_avg("answer_relevancy"),
        context_precision=_avg("context_precision") if use_context else -1.0,
        context_recall=_avg("context_recall") if use_context else -1.0,
        per_query=per_query,
        config=config,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
