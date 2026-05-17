"""
意图分类器
根据用户输入的问题，判断其意图类型，以便后续调用不同的处理管道
"""
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 提示词：告诉模型如何分类
# ============================================================
INTENT_PROMPT = """你是一个法律财税领域的意图分类助手。
请分析用户问题，判断其意图属于以下哪一种：

1. 筹划型：用户想做税务规划、方案设计、交易结构安排
   关键词示例："怎么设计""最优方案""如何筹划""怎么操作可以递延纳税"
   
2. 争议型：用户已面临税务争议、稽查、被税务局质疑
   关键词示例："被查""复议""抗辩""认定不合理""收到通知书"
   
3. 合规型：用户想审查合同、检查风险、评估合规性
   关键词示例："帮我审一下""有什么风险""是否合规""检查一下"
   
4. 知识型：用户纯粹查询法规、政策、税率、概念解释
   关键词示例："是什么""多少""规定""税率""条件"

请严格返回JSON格式，不要加任何其他文字：
{"intent": "类型", "confidence": 0.0~1.0, "reason": "简短原因（10字以内）"}"""


class IntentClassifier:
    """意图分类器：用LLM判断用户问题的意图类型"""

    def __init__(self):
        """初始化LLM客户端"""
        # 使用DeepSeek作为判断模型（也可换成OpenAI）
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        if not api_key:
            raise ValueError("❌ 未配置 DEEPSEEK_API_KEY，请检查 .env 文件")

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def classify(self, query: str) -> dict:
        """
        分类用户查询，返回意图类型和置信度。
        
        参数：
        - query: 用户输入的文本
        
        返回：
        字典，格式 {"intent": "筹划型", "confidence": 0.9, "reason": "涉及交易结构设计"}
        """
        # 调用LLM做意图分类，temperature=0 保证结果稳定
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0
        )

        # 解析返回的JSON字符串
        result_text = response.choices[0].message.content.strip()
        
        # 处理可能的前后缀（LLM有时会在JSON外包上 ```json ... ``` 标记）
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]  # 去掉第一行 ```json
            if result_text.endswith("```"):
                result_text = result_text[:-3]  # 去掉末尾 ```

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # 如果解析失败，默认当作知识型处理
            result = {"intent": "知识型", "confidence": 0.5, "reason": "解析失败降级"}

        return result


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    classifier = IntentClassifier()

    test_queries = [
        "公司股权转让，如何操作可以递延纳税？",
        "我们被税局认定关联交易定价不合理，怎么反驳？",
        "帮我检查一下这份合同的税务风险",
        "研发费用加计扣除的最新比例是多少？",
        "增值税申报期限是每月几号？",
    ]

    for q in test_queries:
        result = classifier.classify(q)
        print(f"\n❓ {q}")
        print(f"   → 意图: {result['intent']}（置信度: {result['confidence']}）")
        print(f"   → 原因: {result['reason']}")