from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ollama (local OpenAI-compatible API). Default off — use GROQ_API_KEY for hosted LLMs.
    ollama_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1:8b"

    # DeepSeek
    deepseek_api_key: SecretStr = SecretStr("")

    # Groq
    groq_api_key: SecretStr = SecretStr("")
    groq_query_model: str = "llama-3.1-8b-instant"
    groq_analysis_model: str = "llama-3.3-70b-versatile"
    groq_report_model: str = "llama-3.3-70b-versatile"

    # Qwen (Alibaba DashScope, OpenAI-compatible endpoint). Used as an INDEPENDENT
    # sufficiency-judge — a different model family from the DeepSeek gatherer, so the
    # verifier does not share the doer's blind spots. Empty key => unused. Base URL is
    # region-specific: intl = dashscope-intl, mainland China = dashscope.aliyuncs.com.
    qwen_api_key: SecretStr = SecretStr("")
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    # Data source API keys
    otx_api_key: SecretStr = SecretStr("")
    # Reserved for the experimental VirusTotal connector — no fetch script
    # consumes it yet (connectors/virustotal.py takes the key directly).
    vt_api_key: SecretStr = SecretStr("")
    whoxy_api_key: SecretStr = SecretStr("")

    # LangSmith
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "rag-cti"
    langchain_tracing_v2: bool = True
    # When tracing is enabled, run LangSmith trace submission in a background thread.
    # Default False: submission is synchronous-but-bounded so a tracing-side 429 cannot
    # leave a background queue blocking process exit (paired with flush_tracers()).
    langchain_callbacks_background: bool = False

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "cti_chunks"

    # Neo4j — CTI-RAG's OWN isolated instance (port 7689), NOT the cti-agent graph
    # on 7687. M4 consumption-layer knowledge-graph backend (DM4-1). See
    # Historical rationale: docs/archive/runtime/HISTORICAL_M4_consumption_langgraph_design.md.
    # Empty password => Neo4j features disabled.
    neo4j_uri: str = "bolt://localhost:7689"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"

    # Embedding (must be a HF repo id or local path; bare "bge-m3" is not valid on the Hub)
    embedding_model: str = "BAAI/bge-m3"

    # Retrieval
    retrieval_top_k: int = 10
    # Dense weight in the weighted-RRF fusion (sparse gets 1 - alpha).
    # 0.5 = symmetric fusion; >= 1.0 skips the sparse retriever (pure dense).
    hybrid_alpha: float = 0.5
    rrf_candidate_multiplier: int = 3

    # Generation — pinned to DeepSeek (same endpoint/key), model-downgrade chain:
    # try generation_models[0] first, fall to the next on a backend failure. Primary
    # deepseek-v4-flash is a reasoning model: it spends the OUTPUT budget on
    # reasoning_content BEFORE writing content. At 1024 a large synthesis context
    # (~6k-token prompt) let reasoning (measured up to ~2400 tok) consume the whole
    # budget -> empty content. Size generously for reasoning + a full answer.
    generation_max_tokens: int = 8192
    generation_models: list[str] = ["deepseek-v4-flash", "deepseek-chat"]

    # LLM client retry/timeout — bounds the 429 failure mode. One retry authority per
    # client (no nested SDK retries multiplying with tenacity), a per-request wall
    # timeout, and a retry-after ceiling above which a 429 is treated as un-recoverable
    # (daily-cap / TPD) so the call fails fast instead of burning the backoff ladder.
    groq_request_timeout: float = 30.0
    deepseek_request_timeout: float = 60.0
    llm_max_retries: int = 2
    retry_after_ceiling_seconds: float = 60.0
    # Concurrency/rate admission control is a core runtime invariant for agentic RAG:
    # every LLM path can be fanned out by query rewrite, supervisor workers, or tool
    # dispatch. Tune concurrency/rate; set both to 0 for passthrough (tests only).
    llm_max_global_concurrency: int = 4
    llm_rate_limit_per_sec: float = 0.0

    # Reranker (hybrid+reranker is the recommended config — see README eval results)
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_candidates_k: int = 50
    # 512 truncates 11.4% of chunks (42% of OTX) against the chunker's
    # 600-token target, BUT it is the CERTIFIED value: the 2026-06-11 A/B
    # measured 640 as retrieval-neutral (hit@k unchanged on query_set_v3)
    # while dropping the technique annotator's CTI-ATE Micro-F1 from the
    # 0.653-0.670 band to 0.564 — the truncated tails hurt CrossEncoder
    # ranking more than they help. Keep 512 unless re-certifying.
    reranker_max_length: int = 512
    # Serialize the cross-encoder forward pass across threads. This is not an
    # experiment flag: any agentic or parallel retrieval path can share one GPU, so
    # predict must be guarded by default.
    reranker_serialize_predict: bool = True

    # Feature flags
    hyde_enabled: bool = True
    hyde_min_query_tokens: int = 5
    hyde_max_tokens: int = 300
    hyde_output_max_chars: int = 2000

    # LLM query rewrite (normalize/decompose/contextualize). Default ON: the
    # four-quadrant A/B (2026-06-16) showed rewrite+HyDE >= HyDE-only on BOTH clean
    # and adversarial technique queries (the clean-set top-1 regression appeared only
    # in the no-HyDE quadrant, which is not the default). Costs one Groq-8b call/query.
    query_rewrite_enabled: bool = True
    query_rewrite_max_subqueries: int = 4
    query_rewrite_max_tokens: int = 300
    # Parallelize sub-query fan-out. This is the mainline behavior for decomposed
    # agentic retrieval: cap it with query_rewrite_max_parallel_subqueries and the
    # provider limiter instead of leaving it hidden behind an off switch.
    query_rewrite_parallel_fanout_enabled: bool = True
    query_rewrite_max_parallel_subqueries: int = 4

    # Constraint routing (soft boost). Reuses the query-rewrite LLM call to extract
    # named entities, plus deterministic technique-id / source-type signals, into a
    # PayloadConstraint that *boosts* (never filters) matching results. Decoupled from
    # query_rewrite_enabled: the deterministic signals still route when rewrite is off.
    constraint_routing_enabled: bool = True
    constraint_boost_weight: float = 0.5
    constraint_boost_fetch_multiplier: int = 1

    # Agentic answer loop (workflow->agentic). This is the mainline answer path:
    # retrieve -> assess sufficiency -> retrieve more -> synthesize. Single-shot
    # remains available only through answer_single_shot() for baselines/fallbacks.
    #
    # Design principle: these are GENEROUS safety backstops against real limits (the
    # model's context window; runaway cost/latency) — NOT task quotas. The loop converges
    # on the judge's sufficiency call + a no-progress stop (a burst that gathers nothing
    # new); the numbers below only catch pathology and should rarely bind.
    agentic_enabled: bool = True
    # PRIMARY convergence bound: how many retrieve_more re-entries the loop allows before it
    # synthesizes with what it has (stop_reason="max_rounds"). This makes latency BOUNDED by
    # design (<= max_retrieve_rounds + 1 bursts) instead of relying on an LLM judge that may
    # never say "sufficient" (a stricter judge can loop forever). Keep small.
    agentic_max_retrieve_rounds: int = 2
    # RUNAWAY backstops — should rarely/never bind now that max_retrieve_rounds is primary.
    # If "budget" shows up as a normal stop_reason, convergence is broken, not these knobs.
    agentic_max_iterations: int = 6
    agentic_token_ceiling: int = 200000
    # Wall-clock tail-latency guardrail (seconds), checked between iterations — the standard
    # max_execution_time companion to the iteration cap, bounds latency when an API hangs.
    # 0 disables it.
    agentic_max_wall_seconds: float = 180.0
    # Inner GATHER loop budget: max LLM tool-calling rounds per burst before the loop
    # stops regardless. The inner agent is gather-ONLY (it populates the ledger and does
    # NOT write the answer — synthesize does), and it stops as soon as it emits no tool
    # call (it judged it has enough), so this only caps pathology. ~8 rounds cover
    # resolve+outline+query plus a couple of retrieves comfortably.
    agentic_max_inner_steps: int = 8
    # The sufficiency judge. ``agentic_verifier_provider`` picks WHICH client builds it:
    # "deepseek" (default) reuses the DeepSeek client — same family as the gatherer, so
    # NOT an independent verifier; "qwen" uses the DashScope client for a cross-family,
    # independent verifier. ``agentic_verifier_model`` must name a model on that provider.
    agentic_verifier_provider: str = "deepseek"
    agentic_verifier_model: str = "deepseek-chat"
    # Judge output budget. The verdict JSON is small, so this is mostly headroom — but a
    # thinking-style verifier (some Qwen models emit reasoning before the JSON) needs room
    # or it returns empty content. 512 was too tight for those; 2048 is safe for both.
    agentic_verifier_max_tokens: int = 2048
    # Generous window-safety bound on prose chunks fed to synthesis (chunks are long).
    # The answer can only cite what reaches synthesis, so this is sized to fit the context
    # window, not an arbitrary small number. Facts are fed in full (no cap).
    agentic_synthesis_top_k: int = 50
    # Window-safety bound for graph facts injected as pseudo-chunks during synthesis.
    # The ledger may gather hundreds of facts for comparison questions; synthesis gets
    # the highest-credibility slice plus structured summaries elsewhere in the prompt.
    agentic_synthesis_fact_limit: int = 120
    # Within-burst context trimming: when > 0, mask all but the most-recent N ToolMessage
    # contents in the model input each turn (their essence is in the state view), cutting
    # the growing-context latency. 0 = disabled (full transcript, current behavior). This
    # is a REMOVAL of context the model used to see, so it stays 0 until eval PROVES the
    # win: recall/F1 unchanged-or-better AND tokens/latency/tool_calls down (else revert).
    agentic_keep_last_observations: int = 0
    # Deterministic convergence guard: stop when open graph categories do not shrink
    # and no new facts arrive. 0 disables the stall rule (always-on when > 0).
    agentic_open_cat_stall_limit: int = 2
    agentic_effort_budgets: dict[str, int] = {"simple": 3, "comparison": 8, "complex": 12}
    # Hard runaway ceilings. These are deliberately much higher than the user-visible
    # guidance budgets; they stop pathological loops without blocking normal multi-round
    # comparison/compound questions.
    agentic_hard_tool_budgets: dict[str, int] = {"simple": 10, "comparison": 20, "complex": 32}
    # Keep semantic-search tool calls query-shaped. ReAct models sometimes paste ledger
    # summaries or gap lists into retrieve(); that bloats rewrite/HyDE latency without adding
    # signal. The graph facts remain full-fidelity in the ledger.
    agentic_retrieve_query_max_chars: int = 360
    # Dispatch independent tool calls in one model turn concurrently. Safety comes
    # from the provider limiter, ledger RLock, and serialized reranker predict.
    agentic_parallel_dispatch_enabled: bool = True
    agentic_max_parallel_tools: int = 2

    # Multi-agent supervisor for compound/parallelizable queries. Kept as an explicit
    # product mode while the single-agent agentic loop remains the default answer path.
    supervisor_enabled: bool = False
    # Max worker sub-agents. Hard cap on total
    # dispatch_worker calls (over-decomposition backstop) AND the ThreadPoolExecutor
    # max_workers for parallel dispatch.
    supervisor_max_branches: int = 4
    # Runaway backstop on supervisor ReAct loop turns (dispatch round(s) + compose + stop
    # fit in a few; this only catches pathology). Analogous to agentic_max_inner_steps.
    supervisor_max_steps: int = 6
    # Composer call output budget. The Composer writes the full combined answer (a CTI
    # comparison can be long), so this is generous; it reuses the agentic_verifier_* client.
    supervisor_compose_max_tokens: int = 4096

    @field_validator("hybrid_alpha")
    @classmethod
    def validate_alpha(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("hybrid_alpha must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_required_secrets(self) -> Settings:
        """HyDE / query-rewrite / generation need an LLM; pure retrieval does not."""
        if not self.hyde_enabled and not self.query_rewrite_enabled:
            return self
        has_ollama = self.ollama_enabled
        has_groq = bool(self.groq_api_key.get_secret_value())
        if not has_ollama and not has_groq:
            raise ValueError(
                "HyDE/query-rewrite is enabled but no LLM provider is configured: "
                "set GROQ_API_KEY or OLLAMA_ENABLED=true for local Ollama, "
                "or disable HYDE_ENABLED / QUERY_REWRITE_ENABLED for retrieval-only."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
