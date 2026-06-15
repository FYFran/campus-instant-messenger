"""
AI论文降重效果验证脚本
TempParaphraser (EMNLP 2025) 技术验证
用DeepSeek API对AI生成论文做多轮高温改写，对比改写前后AIGC特征
"""
import os, json, time, sys, re
from openai import OpenAI

# ── Config ──
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    # fallback: read from pet_config.json
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "pet_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
            API_KEY = cfg.get("deepseek_api_key") or cfg.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com/v1")
MODEL = "deepseek-chat"  # V4-Flash, cheapest

# ── 测试样本: AI生成的论文段落 ──
SAMPLES = [
    {
        "title": "人工智能对高等教育的影响研究",
        "text": """随着人工智能技术的快速发展，其在高等教育领域的应用日益广泛。人工智能技术不仅改变了传统的教学模式，还对教育管理、学生评估等多个方面产生了深远影响。本研究通过文献分析和案例研究，探讨了人工智能在高等教育中的应用现状、存在问题及未来发展趋势。研究发现，人工智能技术可以有效提升教学效率，实现个性化学习，但同时也面临着数据安全、伦理道德等方面的挑战。基于此，本文提出了一系列促进人工智能与高等教育深度融合的对策建议。"""
    },
    {
        "title": "新能源汽车产业发展策略分析",
        "text": """新能源汽车产业作为我国战略性新兴产业，近年来取得了显著的发展成就。在国家政策的大力支持下，新能源汽车产销量持续增长，技术水平不断提升。然而，产业发展仍面临着核心技术突破不足、充电基础设施建设滞后、市场竞争加剧等问题。本文运用SWOT分析方法，系统梳理了新能源汽车产业的优势、劣势、机遇和威胁，并在此基础上提出了针对性的发展策略，包括加大研发投入、完善基础设施、优化产业布局等方面的具体建议。"""
    },
    {
        "title": "企业财务管理数字化转型研究",
        "text": """在数字经济时代背景下，企业财务管理面临着深刻的变革。传统的财务管理模式已难以适应快速变化的市场环境和企业发展需求。数字化转型成为企业财务管理的必然趋势。本文从理论分析和实践案例两个维度，深入探讨了企业财务管理数字化转型的动因、路径和关键成功因素。研究表明，企业需要从战略规划、组织架构、技术应用和人才培养等多个层面协同推进财务管理的数字化转型，才能有效提升财务管理效率和决策支持能力。"""
    },
    {
        "title": "短视频对大学生价值观的影响及对策",
        "text": """短视频平台作为新媒体时代的重要传播渠道，对大学生的思想观念和价值取向产生了不容忽视的影响。短视频内容形式多样、传播速度快、覆盖面广，既丰富了大学生的课余生活，也带来了信息碎片化、价值观多元化等挑战。本文通过问卷调查和深度访谈相结合的研究方法，分析了短视频使用行为与大学生价值观变化之间的关联，并从学校教育、平台治理和学生自律三个层面提出了相应的引导策略，旨在促进大学生形成正确的价值观。"""
    },
    {
        "title": "乡村振兴背景下农村电商发展研究",
        "text": """乡村振兴战略的实施为农村电商的发展提供了重要机遇。农村电商作为连接城乡市场的重要桥梁，在促进农产品销售、增加农民收入、推动农村产业升级等方面发挥着积极作用。然而，农村电商发展仍面临物流体系不完善、人才短缺、品牌建设滞后等现实困境。本文在梳理农村电商发展现状的基础上，分析了制约农村电商发展的关键因素，并从基础设施建设、人才培养、品牌打造和政策支持等方面提出了促进农村电商高质量发展的对策建议。"""
    },
]

# ── 改写策略 (基于TempParaphraser) ──

SYSTEM_PROMPT = """你是学术论文改写专家。任务是对给定的学术文本进行改写，使其更像人类写作。

改写规则:
1. 保持原意不变，不添加或删除信息
2. 改变句式结构: 主动↔被动切换、长短句交替
3. 替换部分词汇为学术同义词
4. 适当调整段落结构，打破AI生成文本的固定模式
5. 保留专业术语、数据、引用格式不变
6. 保持学术风格，但加入自然的行文变化
7. 不要解释你做了什么，只输出改写后的文本

关键: 改写后的文本需要能通过AIGC检测。这意味着:
- 避免过于工整的排比句式
- 加入适当的口语化学术表达
- 句子长度要有变化(有些短句，有些长句)
- 使用更加多样化的过渡词"""

ROUND_CONFIGS = [
    {"name": "Round1-语义改写", "temperature": 0.8, "prompt": "请对以下学术文本进行语义改写，保持原意但改变表达方式。只输出改写后的文本，不要解释。"},
    {"name": "Round2-高温重构", "temperature": 1.3, "prompt": "请对以下文本进行深度改写。大幅改变句式结构，打破原有的表达模式。使用不同的词汇和句式。只输出改写后的文本。"},
    {"name": "Round3-学术润色", "temperature": 0.4, "prompt": "请对以下文本进行学术润色，确保语言流畅、逻辑清晰、表达专业。只输出改写后的文本。"},
]

def rewrite_text(text: str, rounds: list = None) -> dict:
    """多轮改写Pipeline"""
    if rounds is None:
        rounds = ROUND_CONFIGS
    current = text
    results = []
    total_tokens = 0

    for i, cfg in enumerate(rounds):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=cfg["temperature"],
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{cfg['prompt']}\n\n原文:\n{current}"}
                ],
                max_tokens=2048,
            )
            current = resp.choices[0].message.content.strip()
            tokens = resp.usage.total_tokens
            total_tokens += tokens

            results.append({
                "round": cfg["name"],
                "temperature": cfg["temperature"],
                "tokens": tokens,
                "text": current[:200] + "..." if len(current) > 200 else current,
            })

            print(f"    {cfg['name']}: temp={cfg['temperature']}, tokens={tokens}, "
                  f"len {len(text)}→{len(current)}字")
            time.sleep(0.3)  # rate limit

        except Exception as e:
            print(f"    FAIL {cfg['name']}: {e}")
            return {"error": str(e), "results": results}

    return {
        "original": text,
        "rewritten": current,
        "rounds_detail": results,
        "total_tokens": total_tokens,
        "cost_estimate": f"CNY {total_tokens * 0.002 / 1000:.4f} (V4-Flash)",
        "original_len": len(text),
        "rewritten_len": len(current),
    }

def score_readability(text: str) -> dict:
    """简单的文本特征分析"""
    sentences = re.split(r'[。！？；]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return {}

    lengths = [len(s) for s in sentences]
    avg_len = sum(lengths) / len(lengths)

    # 句式多样性 = 句长标准差/平均句长
    if len(lengths) > 1:
        variance = sum((l - avg_len) ** 2 for l in lengths) / (len(lengths) - 1)
        std_dev = variance ** 0.5
        diversity = std_dev / avg_len if avg_len > 0 else 0
    else:
        diversity = 0

    # 词汇多样性 (简化: 基于字符2-gram)
    chars = text.replace("\n", "").replace(" ", "")
    grams = set()
    for i in range(len(chars) - 1):
        grams.add(chars[i:i+2])
    vocab_richness = len(grams) / len(chars) if chars else 0

    return {
        "sentences": len(sentences),
        "avg_sentence_len": round(avg_len, 1),
        "sentence_diversity": round(diversity, 3),
        "vocab_richness": round(vocab_richness, 3),
    }

def main():
    print("=" * 60)
    print("AI论文降重效果验证 — TempParaphraser Pipeline")
    print(f"模型: {MODEL}  样本数: {len(SAMPLES)}")
    print("=" * 60)

    results = []
    total_cost = 0

    for i, sample in enumerate(SAMPLES):
        print(f"\n[{i+1}/{len(SAMPLES)}] {sample['title']}")
        print(f"   原文: {len(sample['text'])}字")

        result = rewrite_text(sample["text"])
        if "error" in result:
            print(f"   SKIP: {result['error']}")
            continue

        # 文本特征对比
        orig_score = score_readability(result["original"])
        new_score = score_readability(result["rewritten"])

        result["original_scores"] = orig_score
        result["rewritten_scores"] = new_score
        result["title"] = sample["title"]

        # 语义保留率(简化: 基于字符集重叠)
        orig_chars = set(result["original"].replace("\n", ""))
        new_chars = set(result["rewritten"].replace("\n", ""))
        overlap = len(orig_chars & new_chars) / len(orig_chars | new_chars) if (orig_chars | new_chars) else 0
        result["char_overlap"] = round(overlap, 3)

        results.append(result)

        print(f"   STATS: avg_sentence_len: {orig_score.get('avg_sentence_len','?')}->{new_score.get('avg_sentence_len','?')} "
              f"| 句式多样性: {orig_score.get('sentence_diversity','?')}→{new_score.get('sentence_diversity','?')} "
              f"| 字符重叠率: {overlap}")
        total_cost += result["total_tokens"] * 0.002 / 1000

    # ── 汇总 ──
    print(f"\n{'=' * 60}")
    print(f"SUMMARY REPORT")
    print(f"{'=' * 60}")
    print(f"成功: {len(results)}/{len(SAMPLES)} 篇")

    if results:
        avg_orig_len = sum(r["original_len"] for r in results) / len(results)
        avg_new_len = sum(r["rewritten_len"] for r in results) / len(results)
        avg_overlap = sum(r["char_overlap"] for r in results) / len(results)

        orig_div = sum(r["original_scores"].get("sentence_diversity", 0) for r in results) / len(results)
        new_div = sum(r["rewritten_scores"].get("sentence_diversity", 0) for r in results) / len(results)

        print(f"平均字数: {avg_orig_len:.0f} → {avg_new_len:.0f} (变化 {(avg_new_len/avg_orig_len-1)*100:+.1f}%)")
        print(f"句式多样性: {orig_div:.3f} → {new_div:.3f} ({(new_div/orig_div-1)*100:+.1f}%)" if orig_div else "")
        print(f"平均字符重叠率: {avg_overlap:.3f} (1.0=完全相同, 0=完全不同)")
        print(f"Estimated API cost: CNY {total_cost:.4f}")

        # 保存详细结果
        out_path = os.path.join(os.path.dirname(__file__), "rewrite_verify_results.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n详细结果已保存: {out_path}")

        # 判断
        print(f"\n{'─' * 60}")
        if avg_overlap < 0.3:
            print("WARN: char_overlap <0.3 — rewrite may have changed meaning too much")
        elif avg_overlap > 0.7:
            print("WARN: char_overlap >0.7 — rewrite may not be strong enough for AIGC reduction")
        else:
            print("OK: char_overlap in reasonable range (0.3-0.7)")

        if new_div > orig_div * 1.1:
            print("OK: sentence diversity improved >10% — TempParaphraser works")
        else:
            print("WARN: sentence diversity improvement insufficient — try adjusting temperature")

if __name__ == "__main__":
    main()
