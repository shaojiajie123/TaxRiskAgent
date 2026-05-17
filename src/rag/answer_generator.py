"""
答案生成器
集成意图分类 + 混合检索 + 意图定制Prompt，生成最终回答
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
from dotenv import load_dotenv
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.intent_classifier import IntentClassifier

load_dotenv()

# ============================================================
# 不同意图的系统提示词
# ============================================================
SYSTEM_PROMPTS = {
    "筹划型": """你是资深税务律师。请基于提供的法规和判例，为用户生成税务筹划方案。
要求：
- 列出2-3个可选方案，对比优劣
- 标明每个方案的法律依据（引用法条号）
- 提示每个方案的潜在风险
- 仅基于提供的知识库文档，不要编造法规""",

    "争议型": """你是税务争议律师。请基于提供的知识，帮用户梳理争议焦点和应对策略。
要求：
- 明确争议涉及的法条
- 找到支持用户的有利判例和规定
- 列出救济途径（行政复议、诉讼等）及程序要点
- 仅基于提供的知识库文档回答""",

    "合规型": """你是企业合规顾问。请基于提供的法规，帮用户识别和评估风险。
要求：
- 逐条对照法规指出不合规之处
- 评估风险等级（高/中/低）
- 给出具体整改建议
- 仅基于提供的知识库文档回答""",

    "知识型": """你是税法知识库助手。请基于提供的规定，准确回答用户问题。
要求：
- 准确引用法条号或文号
- 解释清晰、简洁、易懂
- 如知识库无相关信息，明确指出并建议咨询专业人士
- 仅基于提供的知识库文档回答"""
}


class AnswerGenerator:
    """RAG答案生成器：检索 → 分类 → 生成"""

    def __init__(self):
        """初始化检索器、分类器和LLM客户端"""
        self.retriever = HybridRetriever(alpha=0.5)
        self.classifier = IntentClassifier()

        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def answer(self, query: str) -> dict:
        """
        处理用户问题，返回完整回答及元信息。
        
        返回值：
        {
            "query": 原始问题,
            "intent": 意图类型,
            "confidence": 置信度,
            "documents": 检索到的相关法规,
            "answer": 生成的回答
        }
        """
        # ---- 第1步：意图分类 ----
        intent_info = self.classifier.classify(query)
        intent = intent_info["intent"]
        confidence = intent_info["confidence"]
        print(f"   🏷️  意图: {intent} (置信度: {confidence})")

        # ---- 第2步：根据意图调整检索权重 ----
        # 知识型偏重关键词精确匹配，筹划/合规型偏重语义广度
        if intent == "知识型":
            self.retriever.set_alpha(0.7)      # BM25权重更高 → 法条号匹配更准
        elif intent in ("筹划型", "合规型"):
            self.retriever.set_alpha(0.3)      # 向量权重更高 → 语义覆盖面更广
        else:
            self.retriever.set_alpha(0.5)      # 争议型保持均衡

        # ---- 第3步：混合检索 ----
        results = self.retriever.retrieve(query, top_k=5) # results = [(文本1，得分，元数据),(文本2，得分，元数据),(),...]

        # 将检索到的法规拼接为上下文
        context_parts = []
        for doc_content, score, meta in results:  # 元组拆包 
            title = meta.get("title", "未知来源")
            context_parts.append(f"[来源: {title}]\n{doc_content}")
        context = "\n\n---\n\n".join(context_parts)

        # ---- 第4步：组装Prompt并生成回答 ----  
        system_prompt = SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["知识型"])  # 字典.get(键,默认值) -> 取出字典中键对应的值，值不存在的话就使用默认值  选择用户意图所对应的系统提示词

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[                                          # 系统提示词：定义AI是谁，履行什么职责，遵循什么原则  用户提示词：提供本次对话需要处理的具体信息，告诉AI要做什么，以及手里有什么材料
                {"role": "system", "content": system_prompt},  # 根据意图 systme_prompt 和检索结果 context ，写出最合适的回答
                {"role": "user", "content": f"知识库文档：\n{context}\n\n用户问题：{query}\n\n请回答："}   # 最终检索到的知识与用户提问一同拼接并注入到用户提示词中！而不是系统提示词中！
            ],
            temperature=0.2  # 较低的温度保证答案准确稳定
        )

        answer_text = response.choices[0].message.content

        # ---- 第5步：返回完整结果 ----
        return {
            "query": query,
            "intent": intent,
            "confidence": confidence,
            "documents": [(doc, score, meta) for doc, score, meta in results],   # 列表推导式 + 元组拆包  将results 的内容照搬到新的列表中返回，这样有利于信息的隔离，防止外部篡改本模块的数据
            "answer": answer_text
        }


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    generator = AnswerGenerator()

    print("=" * 60)
    print("  法律财税 RAG 助手 - 测试")
    print("=" * 60)

    test_queries = [
        "增值税申报期限是每月几号？",
        "发票备注栏没填写有什么后果？",
    ]

    for q in test_queries:
        print(f"\n{'─' * 60}")
        print(f"❓ 问：{q}")
        print(f"{'─' * 60}")
        result = generator.answer(q)
        print(f"📝 答：\n{result['answer']}")
        print(f"\n📎 引用法规：")
        for doc, score, meta in result["documents"]:
            title = meta.get("title", "未知")
            print(f"   · {title} (相关度: {score:.2f})")