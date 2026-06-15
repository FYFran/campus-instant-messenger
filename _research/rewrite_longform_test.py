"""
长文改写效果测试 — 模拟真实论文章节
测试: 5000-15000字论文，分段改写，质量一致性
"""
import os, json, time, re, sys
from openai import OpenAI

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "pet_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            API_KEY = json.load(f).get("deepseek_api_key") or json.load(f).get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set"); sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com/v1")
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是学术论文改写专家。对以下段落进行改写，降低AI生成文本特征。

核心规则:
1. 保持原意和学术严谨性不变
2. 改变句式结构 — 主动被动切换，长短句交替
3. 替换部分词汇为学术同义词
4. 打破AI文本的固定模式(排比、套路句式)
5. 保留专业术语、数据、引用
6. 加入自然行文变化
7. 只输出改写后文本，不要解释"""

ROUNDS = [
    ("语义改写", 0.8, "请对以下学术文本进行语义改写，改变表达方式但保持原意。只输出改写后文本:"),
    ("高温重构", 1.3, "请深度改写以下文本。大幅改变句式，打破原有表达模式，使用不同词汇。只输出改写后文本:"),
    ("学术润色", 0.4, "请对以下文本进行学术润色，确保流畅、逻辑清晰、表达专业。只输出改写后文本:"),
]

# ── 生成长文样本 ──
def generate_sample_paper(title: str, sections: list, total_words: int) -> str:
    """Generate a full-length AI-written paper section by section"""
    paper = f"# {title}\n\n"
    words_per_section = total_words // len(sections)

    for i, (heading, prompt) in enumerate(sections):
        print(f"  Generating section {i+1}/{len(sections)}: {heading} ({words_per_section}w)...")
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": f"你是中国大学毕业生，正在写毕业论文。题目: {title}。写一段学术论文内容，约{words_per_section}字。用规范的学术语言，符合本科毕业论文水平。"},
                    {"role": "user", "content": f"请撰写论文章节「{heading}」: {prompt}"}
                ],
                max_tokens=4096,
            )
            text = resp.choices[0].message.content.strip()
            paper += f"## {heading}\n\n{text}\n\n"
            time.sleep(0.5)
        except Exception as e:
            print(f"  FAIL: {e}")
            paper += f"## {heading}\n\n[生成失败: {e}]\n\n"

    return paper

def chunk_text(text: str, max_chars: int = 1200) -> list:
    """Split text by paragraphs, keeping chunks under max_chars"""
    paragraphs = text.split('\n')
    chunks, current = [], ""
    for p in paragraphs:
        if p.strip().startswith('#'):
            if current: chunks.append(current)
            chunks.append(p)  # headings stay separate
            current = ""
        elif len(current) + len(p) > max_chars and current:
            chunks.append(current)
            current = p
        else:
            current = (current + '\n' + p) if current else p
    if current:
        chunks.append(current)
    return chunks

def rewrite_chunk(text: str, chunk_idx: int, total: int) -> tuple:
    """3-round rewrite on a single chunk"""
    current = text
    tokens_used = 0
    for name, temp, prompt in ROUNDS:
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=temp,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{prompt}\n\n原文:\n{current}"}
                ],
                max_tokens=4096,
            )
            current = resp.choices[0].message.content.strip()
            tokens_used += resp.usage.total_tokens
            time.sleep(0.3)
        except Exception as e:
            print(f"    Chunk {chunk_idx}/{total} round {name} FAIL: {e}")
            return text, tokens_used
    return current, tokens_used

def main():
    title = "人工智能在高校图书馆智慧服务中的应用研究"
    sections = [
        ("绪论", "介绍研究背景（AI技术发展+图书馆数字化转型）、研究意义、研究方法（文献研究+案例分析）、论文结构。约800字。"),
        ("文献综述", "综述国内外关于AI在图书馆应用的研究现状，包括智能推荐、知识图谱、自然语言处理等方面。引用近年文献。约1500字。"),
        ("相关技术概述", "介绍本论文涉及的核心技术：自然语言处理、推荐算法、知识图谱、深度学习等。说明技术原理和在图书馆场景的适用性。约1200字。"),
        ("高校图书馆智慧服务现状分析", "分析当前高校图书馆服务的现状和存在的问题：资源发现困难、个性化不足、咨询效率低等。用数据和案例支撑。约1500字。"),
        ("基于AI的智慧图书馆服务系统设计", "提出系统架构设计：智能检索模块、个性化推荐模块、智能问答模块、知识图谱模块。详细描述各模块功能和交互。约2000字。"),
        ("系统实现与关键技术", "描述原型系统的实现：技术选型（Python/Django/Neo4j/BERT）、核心代码逻辑、数据库设计、API接口。约1800字。"),
        ("系统测试与效果评估", "描述测试方法（用户测试+性能测试）、测试结果（准确率/召回率/响应时间）、用户满意度调查。用图表数据说明。约1500字。"),
        ("结论与展望", "总结研究成果、指出研究局限性（数据量有限/未大规模部署）、展望未来研究方向（多模态/大语言模型）。约800字。"),
    ]

    print("=" * 60)
    print("AI论文降重 — 长文效果测试")
    print(f"论文: {title}")
    print(f"目标: ~11000字, 8个章节")
    print("=" * 60)

    # Step 1: Generate sample
    print("\n[Step 1] 生成AI论文样本...")
    paper = generate_sample_paper(title, sections, total_words=11000)
    total_chars = len(paper)
    # Count Chinese characters
    chinese_chars = len(re.findall(r'[一-鿿]', paper))
    print(f"  生成完成: {total_chars} 字符, ~{chinese_chars} 汉字\n")

    # Save original
    orig_path = os.path.join(os.path.dirname(__file__), "sample_original.txt")
    with open(orig_path, 'w', encoding='utf-8') as f:
        f.write(paper)

    # Step 2: Chunk and rewrite
    print("[Step 2] 分段改写 (每段≤1200字)...")
    chunks = chunk_text(paper)
    print(f"  共 {len(chunks)} 段")

    rewritten_chunks = []
    total_tokens = 0
    for i, chunk in enumerate(chunks):
        # Skip headings (keep unchanged)
        if chunk.strip().startswith('#') and len(chunk) < 100:
            rewritten_chunks.append(chunk)
            continue

        chinese_in_chunk = len(re.findall(r'[一-鿿]', chunk))
        print(f"  [{i+1}/{len(chunks)}] ~{chinese_in_chunk}汉字...", end=' ', flush=True)
        new_text, tokens = rewrite_chunk(chunk, i+1, len(chunks))
        rewritten_chunks.append(new_text)
        total_tokens += tokens
        print(f"OK ({tokens}t)")

    # Step 3: Assemble
    rewritten_paper = '\n\n'.join(rewritten_chunks)
    orig_chinese = len(re.findall(r'[一-鿿]', paper))
    new_chinese = len(re.findall(r'[一-鿿]', rewritten_paper))

    # Save rewritten
    new_path = os.path.join(os.path.dirname(__file__), "sample_rewritten.txt")
    with open(new_path, 'w', encoding='utf-8') as f:
        f.write(rewritten_paper)

    # Step 4: Report
    cost = total_tokens * 0.002 / 1000
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"原文汉字: {orig_chinese}")
    print(f"改写后汉字: {new_chinese} ({'+' if new_chinese >= orig_chinese else ''}{new_chinese - orig_chinese}, {(new_chinese/orig_chinese-1)*100:+.1f}%)")
    print(f"总Token: {total_tokens}")
    print(f"API费用: CNY {cost:.4f} (V4-Flash)")
    print(f"预估10000字论文费用: CNY {cost/orig_chinese*10000:.4f}")
    print(f"预估50000字论文章费用: CNY {cost/orig_chinese*50000:.4f}")
    print(f"\n原文: {orig_path}")
    print(f"改写: {new_path}")

if __name__ == "__main__":
    main()
