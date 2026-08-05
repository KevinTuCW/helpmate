"""RAGAS generation-quality metrics with GLM as judge and Qwen3 embeddings.
Consumes the `_eval_row` payloads collected by run_eval.evaluate() when
eval_generate is enabled. Imports are lazy so the module loads without ragas."""
from helpmate.config import get_settings


def _judge_llm():
    from langchain_openai import ChatOpenAI
    s = get_settings()
    return ChatOpenAI(model=s.llm_model, base_url=s.resolved_base_url(),
                      api_key=s.resolved_api_key(), temperature=0)


def _embeddings():
    from langchain_openai import OpenAIEmbeddings
    s = get_settings()
    return OpenAIEmbeddings(model=s.embed_model, base_url=s.embed_base_url(),
                            api_key=s.embed_api_key(), dimensions=s.embed_dim,
                            check_embedding_ctx_length=False)


def run_ragas(eval_rows: list[dict]) -> dict:
    """eval_rows: list of {question, answer, contexts, ground_truth}."""
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    ds = Dataset.from_list([
        {"question": r["question"], "answer": r["answer"],
         "contexts": r["contexts"], "ground_truth": r["ground_truth"]}
        for r in eval_rows])
    result = evaluate(
        ds, metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=LangchainLLMWrapper(_judge_llm()),
        embeddings=LangchainEmbeddingsWrapper(_embeddings()),
    )
    df = result.to_pandas()
    return {m: round(float(df[m].mean()), 4) for m in
            ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
            if m in df.columns}
