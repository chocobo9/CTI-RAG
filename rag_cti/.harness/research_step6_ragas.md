## 搜索记录
- "ragas 0.4 evaluate SingleTurnSample EvaluationDataset": RAGAS official repo, multiple examples
- "ragas deepseek openai-compatible judge llm": GitHub issues #2560, #1432 — OpenAI-compatible via langchain_openai
- "ragas faithfulness answer_relevancy metrics python": Official docs, multiple RAG eval repos

## 方案对比
| 方案 | 来源 | 优点 | 缺点 | 可复用度 |
|------|------|------|------|----------|
| RAGAS 0.4.3 native (SingleTurnSample + evaluate) | ragas official | 已安装(0.4.3), Pydantic v2 based, async support | API changed significantly from v0.1 | 高 — 直接用 |
| LangchainLLMWrapper + ChatOpenAI | ragas.llms + langchain_openai | DeepSeek 支持好, OpenAI-compatible | 需要 langchain 依赖(已装) | 高 |
| llm_factory + OpenAI client | ragas.llms.llm_factory | 更轻量 | 文档少, 可能不稳定 | 中 |

## 推荐
选择 RAGAS 0.4.3 native API + LangchainLLMWrapper 方案。理由：
1. 已安装 0.4.3，langchain-openai 也已装
2. LangchainLLMWrapper 是 RAGAS 文档推荐的 custom LLM 接入方式
3. DeepSeek 通过 ChatOpenAI(base_url=...) 接入，社区有成功案例

## 可移植的具体资源
- RAGAS 0.4.3 API: `from ragas import evaluate, SingleTurnSample, EvaluationDataset`
- Metrics: `from ragas.metrics import Faithfulness, AnswerRelevancy` (或 `ragas.metrics.collections`)
- LLM wrapper: `from ragas.llms import LangchainLLMWrapper`
- Embeddings: `from ragas.embeddings import LangchainEmbeddingsWrapper`
- SingleTurnSample fields: user_input, retrieved_contexts, response, reference
- DeepSeek接入: `ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com/v1", api_key=...)`
- AnswerRelevancy 需要 embeddings — 用项目已有的 HuggingFace embeddings
