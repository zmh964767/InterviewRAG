"""RAGAS 评估脚本

使用 RAGAS 框架评估 RAG 系统的四项核心指标：
- Faithfulness（忠实度）
- Answer Relevancy（答案相关性）
- Context Precision（上下文精确度）
- Context Recall（上下文召回率）
"""

import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


async def run_evaluation():
    """运行 RAGAS 评估"""

    # 1. 加载评估数据集
    eval_path = Path(__file__).parent / "eval_dataset.json"
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    # 过滤掉无关题（无关题没有 ground_truth 上下文）
    eval_items = [item for item in eval_data if item["type"] != "irrelevant"]

    logger.info(f"加载 {len(eval_items)} 道评估题")

    # 2. 初始化 RAG 服务
    from app.services.rag_service import RAGService

    rag_service = RAGService()

    # 3. 运行 RAG 获取预测
    questions = []
    answers = []
    contexts = []
    ground_truths = []

    for item in eval_items:
        question = item["question"]
        ground_truth = item["ground_truth"]

        try:
            result = await rag_service.query(question)
            answer = result["answer"]
            context_texts = [s.get("text", "") for s in result.get("sources", [])]
        except Exception as e:
            logger.error(f"查询失败: {question}: {e}")
            answer = "查询失败"
            context_texts = []

        questions.append(question)
        answers.append(answer)
        contexts.append(context_texts)
        ground_truths.append(ground_truth)

    # 4. 构建 RAGAS 评估数据集
    try:
        from datasets import Dataset

        eval_dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        })

        # 5. 运行 RAGAS 评估
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )

        result = evaluate(
            dataset=eval_dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
        )

        # 6. 输出报告
        print("\n" + "=" * 60)
        print("RAGAS 评估报告")
        print("=" * 60)
        print(f"评估题目数: {len(eval_items)}")
        print("-" * 60)
        for metric, score in result.items():
            print(f"{metric:25s} : {score:.4f}")
        print("=" * 60)

        # 保存结果
        output_path = Path(__file__).parent / "eval_results.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metrics": {k: float(v) for k, v in result.items()},
                    "num_questions": len(eval_items),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(f"评估结果已保存到 {output_path}")

    except ImportError as e:
        logger.error(f"缺少依赖: {e}. 请运行: pip install ragas datasets")
    except Exception as e:
        logger.error(f"评估失败: {e}", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_evaluation())
