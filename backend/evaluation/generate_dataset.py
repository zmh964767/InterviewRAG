"""评估数据集生成脚本

从知识库提取 exact 类型 + LLM 生成 paraphrase / complex 类型。
输出到 eval_dataset_generated.json。

用法：
  cd D:/Zerobyheart/InterviewRAG/backend
  python -m evaluation.generate_dataset
"""

import json
import logging
import re
import sys
import time
from pathlib import Path

# 确保 backend 在 sys.path 中，支持独立运行
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────
KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "questions.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "eval_dataset_generated.json"
CHECKPOINT_PATH = Path(__file__).resolve().parent / "_checkpoint.json"

# 保留的无关题（硬编码，与原 eval_dataset.json 一致）
IRRELEVANT_QUESTIONS = [
    {
        "id": "irrel_001",
        "type": "irrelevant",
        "question": "如何用微波炉烤面包？",
        "ground_truth": "无关题，应拒答",
        "category": "无关",
        "source": "manual",
    },
    {
        "id": "irrel_002",
        "type": "irrelevant",
        "question": "今天天气怎么样？",
        "ground_truth": "无关题，应拒答",
        "category": "无关",
        "source": "manual",
    },
    {
        "id": "irrel_003",
        "type": "irrelevant",
        "question": "法国的首都是哪里？",
        "ground_truth": "无关题，应拒答",
        "category": "无关",
        "source": "manual",
    },
    {
        "id": "irrel_004",
        "type": "irrelevant",
        "question": "推荐一部好看的电影",
        "ground_truth": "无关题，应拒答",
        "category": "无关",
        "source": "manual",
    },
    {
        "id": "irrel_005",
        "type": "irrelevant",
        "question": "怎么做红烧肉？",
        "ground_truth": "无关题，应拒答",
        "category": "无关",
        "source": "manual",
    },
]

# LLM 调用间隔（秒），智谱 API 限速保护
API_DELAY = 1.5


# ── LLM 客户端 ────────────────────────────────────────────
def _create_sync_client():
    """创建同步 OpenAI 兼容客户端（指向智谱）"""
    from app.config import get_settings

    settings = get_settings()
    if not settings.zhipu_api_key:
        raise RuntimeError("缺少 ZHIPU_API_KEY，请在 .env 中配置")

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("缺少 openai 包，请运行: pip install openai")

    return OpenAI(
        api_key=settings.zhipu_api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        timeout=settings.llm_timeout_s,
    )


def _llm_call(client, prompt: str, max_tokens: int = 2048) -> str:
    """调用 LLM 并返回文本"""
    from app.config import get_settings

    settings = get_settings()
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


# ── JSON 解析 ──────────────────────────────────────────────
def _extract_json_array(text: str) -> list | None:
    """从 LLM 输出中提取 JSON 数组（容错处理）

    尝试策略：
    1. 直接 json.loads
    2. 提取 ```json ... ``` 代码块
    3. 提取第一个 [ ... ] 块
    """
    text = text.strip()

    # 策略 1：直接解析
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # 策略 2：提取 markdown 代码块
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            result = json.loads(m.group(1).strip())
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # 策略 3：提取第一个 [ ... ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(text[start : end + 1])
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return None


# ── Checkpoint 管理 ────────────────────────────────────────
def _save_checkpoint(data: list[dict]):
    """保存中间结果到 checkpoint 文件"""
    CHECKPOINT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_checkpoint() -> list[dict] | None:
    """加载 checkpoint（如果存在）"""
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


# ── Step 1：从知识库提取 exact 类型 ────────────────────────
def extract_exact_questions() -> list[dict]:
    """从 questions.json 提取所有问题作为 exact 类型"""
    if not KNOWLEDGE_BASE_PATH.exists():
        raise FileNotFoundError(f"知识库文件不存在: {KNOWLEDGE_BASE_PATH}")

    data = json.loads(KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8"))
    exact_questions = []

    for i, item in enumerate(data):
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()
        category = item.get("category", "未分类")

        if not question or not answer:
            logger.warning(f"跳过空题目: {item.get('id', '?')}")
            continue

        exact_questions.append(
            {
                "id": f"exact_{i + 1:03d}",
                "type": "exact",
                "question": question,
                "ground_truth": answer,
                "category": category,
                "source": "knowledge_base",
            }
        )

    return exact_questions


# ── Step 2：LLM 生成 paraphrase 类型 ──────────────────────
def generate_paraphrases(client, exact_question: str) -> list[str]:
    """用 LLM 对一个问题生成 2 个口语化改写"""
    prompt = f"""把下面的问题改写成 2 个不同的口语化表述，保持原意。
原问题：{exact_question}

规则：
1. 保持原意，不引入新概念
2. 覆盖同义表达、口语和书面语互换
3. 每行一个变体，不要编号、不要解释、不要其他多余文字"""

    text = _llm_call(client, prompt, max_tokens=512)

    # 按行拆分，过滤空行
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    # 去掉可能的编号前缀（如 "1. "、"2. "、"- "）
    cleaned = []
    for line in lines:
        line = re.sub(r"^[\d]+[.、)\]]\s*", "", line)
        line = line.strip("-* ")
        if line and len(line) > 3:
            cleaned.append(line)

    return cleaned[:2]  # 最多取 2 个


def build_paraphrase_questions(
    client, exact_questions: list[dict]
) -> list[dict]:
    """为所有 exact 问题生成 paraphrase 变体"""
    paraphrases = []
    total = len(exact_questions)

    for idx, eq in enumerate(exact_questions):
        try:
            variants = generate_paraphrases(client, eq["question"])
            for j, v in enumerate(variants):
                paraphrases.append(
                    {
                        "id": f"para_{eq['id']}_{j}",
                        "type": "paraphrase",
                        "question": v,
                        "ground_truth": eq["ground_truth"],
                        "category": eq["category"],
                        "source": "llm_generated",
                    }
                )
            logger.info(f"[{idx + 1}/{total}] paraphrase: {eq['id']} -> {len(variants)} 个变体")
        except Exception as e:
            logger.error(f"[{idx + 1}/{total}] paraphrase 失败: {eq['id']} - {e}")

        # 限速
        if idx < total - 1:
            time.sleep(API_DELAY)

        # 每 10 条保存一次 checkpoint
        if (idx + 1) % 10 == 0:
            _save_checkpoint(paraphrases)
            logger.info(f"  checkpoint 已保存 ({len(paraphrases)} 条 paraphrase)")

    return paraphrases


# ── Step 3：LLM 生成 complex 类型 ──────────────────────────
def generate_complex_for_category(
    client, category: str, knowledge_points: list[str]
) -> list[dict]:
    """为一个类别生成 5 个 complex 问题（需综合 2-3 个知识点）"""
    points_text = "\n".join(f"- {kp}" for kp in knowledge_points)
    prompt = f"""根据下面类别的知识点，生成 5 个需要综合多个知识点的面试问题。

类别：{category}
知识点：
{points_text}

规则：
1. 每个问题需要涉及 2-3 个知识点的交叉
2. 问题要具体，不要太宽泛
3. 每个问题附带标准答案（2-3 句话概括核心要点）

请严格按以下 JSON 数组格式输出，不要有其他文字：
[
  {{"question": "...", "answer": "..."}},
  ...
]"""

    text = _llm_call(client, prompt, max_tokens=2048)
    items = _extract_json_array(text)

    if not items:
        logger.warning(f"complex 生成 JSON 解析失败: {category}")
        return []

    results = []
    for item in items:
        q = item.get("question", "").strip()
        a = item.get("answer", "").strip()
        if q and a:
            results.append({"question": q, "answer": a})

    return results


def build_complex_questions(
    client, exact_questions: list[dict], paraphrases: list[dict] | None = None,
) -> list[dict]:
    """为每个类别生成 complex 问题

    Args:
        client: LLM 客户端
        exact_questions: exact 问题列表
        paraphrases: paraphrase 列表（用于 checkpoint 保存，包含 paraphrases+complex）
    """
    # 按类别分组，提取每个类别的问题标题作为知识点
    category_points: dict[str, list[str]] = {}
    for eq in exact_questions:
        cat = eq["category"]
        if cat not in category_points:
            category_points[cat] = []
        # 用问题的前 50 字作为知识点摘要
        category_points[cat].append(eq["question"][:50])

    complex_questions = []
    counter = 0

    for cat, points in category_points.items():
        # 每类最多用 10 个知识点
        selected_points = points[:10]
        try:
            raw_items = generate_complex_for_category(client, cat, selected_points)
            for item in raw_items:
                counter += 1
                complex_questions.append(
                    {
                        "id": f"complex_{counter:03d}",
                        "type": "complex",
                        "question": item["question"],
                        "ground_truth": item["answer"],
                        "category": cat,
                        "source": "llm_generated",
                    }
                )
            logger.info(f"complex: {cat} -> {len(raw_items)} 个问题")
        except Exception as e:
            logger.error(f"complex 失败: {cat} - {e}")

        # checkpoint: 保存 paraphrases + 已生成的 complex
        if paraphrases is not None:
            _save_checkpoint(paraphrases + complex_questions)
            logger.info(f"  checkpoint 已保存 ({len(paraphrases)} para + {len(complex_questions)} complex)")

        time.sleep(API_DELAY)

    return complex_questions


# ── Checkpoint 恢复辅助 ────────────────────────────────────
def _get_exact_id_from_para_id(para_id: str) -> str:
    """从 paraphrase ID 中提取对应的 exact ID

    para ID 格式: para_exact_NNN_j → exact_NNN
    """
    parts = para_id.split("_")
    if len(parts) >= 4 and parts[0] == "para":
        return parts[1] + "_" + parts[2]
    return ""


def _recover_paraphrases_from_checkpoint(
    checkpoint: list[dict], exact_questions: list[dict],
) -> tuple[list[dict], list[dict] | None]:
    """从 checkpoint 恢复 paraphrase 进度

    Returns:
        (paraphrases, remaining_exact): 已完成的 paraphrase 和剩余的 exact 题
        remaining_exact 为 None 表示全部完成
    """
    checkpoint_paras = [item for item in checkpoint if item["type"] == "paraphrase"]
    existing_exact_ids = set()
    for item in checkpoint_paras:
        eid = _get_exact_id_from_para_id(item["id"])
        if eid:
            existing_exact_ids.add(eid)

    remaining = [eq for eq in exact_questions if eq["id"] not in existing_exact_ids]
    if remaining:
        logger.info(
            "  从 checkpoint 恢复（%d 条 paraphrase），还需处理 %d 条",
            len(checkpoint_paras), len(remaining),
        )
        return checkpoint_paras, remaining
    else:
        logger.info("  paraphrase 已全部完成")
        return checkpoint_paras, None


def _log_summary(all_questions: list[dict]) -> None:
    """输出生成结果统计"""
    type_counts = {}
    cat_counts = {}
    for q in all_questions:
        t = q["type"]
        c = q["category"]
        type_counts[t] = type_counts.get(t, 0) + 1
        cat_counts[c] = cat_counts.get(c, 0) + 1

    logger.info("=" * 60)
    logger.info("生成结果统计:")
    logger.info(f"  总计: {len(all_questions)} 个问题")
    for t, n in sorted(type_counts.items()):
        logger.info(f"  类型 {t}: {n} 个")
    for c, n in sorted(cat_counts.items()):
        logger.info(f"  类别 {c}: {n} 个")


# ── Step 2 封装（含 checkpoint 恢复）──────────────────────
def _run_step2_paraphrases(
    client, exact_questions: list[dict], checkpoint: list[dict] | None,
) -> list[dict]:
    """Step 2: LLM 生成 paraphrase，带 checkpoint 恢复"""
    logger.info("Step 2: 用 LLM 生成 paraphrase 类型...")

    if checkpoint:
        paraphrases, remaining = _recover_paraphrases_from_checkpoint(checkpoint, exact_questions)
        if remaining is not None:
            new_paraphrases = build_paraphrase_questions(client, remaining)
            paraphrases = paraphrases + new_paraphrases
    else:
        paraphrases = build_paraphrase_questions(client, exact_questions)

    logger.info(f"  生成 paraphrase: {len(paraphrases)} 个")
    return paraphrases


# ── Step 3 封装（含 checkpoint 恢复）──────────────────────
def _run_step3_complex(
    client, exact_questions: list[dict], paraphrases: list[dict],
) -> list[dict]:
    """Step 3: LLM 生成 complex 类型"""
    logger.info("Step 3: 用 LLM 生成 complex 类型...")
    complex_questions = build_complex_questions(client, exact_questions, paraphrases=paraphrases)
    logger.info(f"  生成 complex: {len(complex_questions)} 个")
    return complex_questions


# ── Main ──────────────────────────────────────────────────
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    logger.info("=" * 60)
    logger.info("评估数据集生成脚本")
    logger.info("=" * 60)

    # Step 1: 提取 exact
    logger.info("Step 1: 从知识库提取 exact 类型...")
    exact_questions = extract_exact_questions()
    logger.info(f"  提取 exact: {len(exact_questions)} 个")

    # 检查是否有 checkpoint
    checkpoint = _load_checkpoint()
    if checkpoint:
        logger.info(f"  发现 checkpoint: {len(checkpoint)} 条已生成数据")

    client = _create_sync_client()

    # Step 2: LLM 生成 paraphrase（含 checkpoint 恢复）
    paraphrases = _run_step2_paraphrases(client, exact_questions, checkpoint)

    # Step 3: LLM 生成 complex
    complex_questions = _run_step3_complex(client, exact_questions, paraphrases)

    # Step 4: 合并所有数据
    all_questions = exact_questions + paraphrases + complex_questions + IRRELEVANT_QUESTIONS

    # 统计输出
    _log_summary(all_questions)

    # Step 5: 保存
    OUTPUT_PATH.write_text(
        json.dumps(all_questions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"已保存到: {OUTPUT_PATH}")

    # 清理 checkpoint
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        logger.info("checkpoint 已清理")

    logger.info("完成!")




if __name__ == "__main__":
    main()
