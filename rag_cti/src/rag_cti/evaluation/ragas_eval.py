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
    per_query: list[dict] = field(default_factory=list)
    config: str = ""
    timestamp: str = ""


def answers_to_ragas_dataset(
    answers: list[GeneratedAnswer],
) -> list[dict]:
    """Convert GeneratedAnswer list to RAGAS SingleTurnSample-compatible dicts.

    Returns a list of dicts with keys: user_input, retrieved_contexts, response.
    """
    samples = []
    for a in answers:
        contexts = [r.document.content for r in a.query_result.results]
        samples.append(
            {
                "user_input": a.query,
                "retrieved_contexts": contexts,
                "response": a.answer,
            }
        )
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
) -> RagasEvalResult:
    """Run RAGAS faithfulness + answer_relevancy on a list of GeneratedAnswers."""
    if settings is None:
        from rag_cti.config import get_settings
        settings = get_settings()

    sample_dicts = answers_to_ragas_dataset(answers)
    if not sample_dicts:
        return RagasEvalResult(
            n_queries=0,
            faithfulness=0.0,
            answer_relevancy=0.0,
            config=config,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    from ragas import SingleTurnSample, EvaluationDataset, evaluate
    from ragas.metrics import Faithfulness, AnswerRelevancy

    llm = _build_judge_llm(settings)
    embeddings = _build_embeddings()

    samples = [
        SingleTurnSample(
            user_input=s["user_input"],
            retrieved_contexts=s["retrieved_contexts"],
            response=s["response"],
        )
        for s in sample_dicts
    ]
    dataset = EvaluationDataset(samples=samples)

    logger.info("running ragas eval", n_queries=len(samples), config=config)

    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(llm=llm), AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=1)],
        show_progress=True,
    )

    df = result.to_pandas()

    per_query = []
    for i, row in df.iterrows():
        per_query.append(
            {
                "question": sample_dicts[i]["user_input"],
                "faithfulness": float(row.get("faithfulness", 0.0)),
                "answer_relevancy": float(row.get("answer_relevancy", 0.0)),
            }
        )

    faith_scores = [pq["faithfulness"] for pq in per_query]
    relevancy_scores = [pq["answer_relevancy"] for pq in per_query]
    avg_faith = sum(faith_scores) / len(faith_scores) if faith_scores else 0.0
    avg_relevancy = sum(relevancy_scores) / len(relevancy_scores) if relevancy_scores else 0.0

    return RagasEvalResult(
        n_queries=len(samples),
        faithfulness=round(avg_faith, 4),
        answer_relevancy=round(avg_relevancy, 4),
        per_query=per_query,
        config=config,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
