"""
任务规划器 - 让 LLM 自主拆解任务步骤
核心变化：不再由人预写死流程，而是 LLM 根据可用工具列表自己写执行计划
"""
import os
import sys
import json

# 将项目根目录加入系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ================================================================
# 可用工具清单（告诉 LLM 它可以调用哪些工具）
# ================================================================
AVAILABLE_TOOLS = """
可用工具列表：

1. analyze_finance(file_path: str)
   - 功能：加载Excel财务报表，执行税务合规检查
   - 输入：财务数据文件的路径
   - 输出：风险列表（每条包含：业务名称、风险等级、问题描述、法律依据、整改建议）

2. search_law(query: str)
   - 功能：在财税法规知识库中检索相关法规全文
   - 输入：查询关键词
   - 输出：相关法规的标题和全文内容

3. generate_advice(risk_info: dict)
   - 功能：针对一条具体的税务风险，生成专业的整改建议
   - 输入：风险字典（包含业务名称、问题描述、法律依据）
   - 输出：包含风险分析、整改建议、总结的结构化建议文本

4. generate_report(summary: str, risks: list)
   - 功能：将分析结果和风险列表整合为最终报告
   - 输入：执行摘要文本 + 风险列表
   - 输出：格式化的最终报告文本
"""

# ================================================================
# 规划提示词：告诉 LLM 如何根据任务写出执行计划
# ================================================================
PLANNING_PROMPT = f"""你是一个AI任务规划专家。你负责根据用户的任务描述，制定一个分步执行计划。

{AVAILABLE_TOOLS}

用户任务：{{task}}

请分析这个任务，并制定一个逐步执行计划。计划必须符合以下规则：
1. 每一步只能调用一个工具
2. 每一步必须明确写出要调用的工具名称和参数
3. 步骤之间如果有依赖关系（比如上一步的输出是下一步的输入），请在说明里标注
4. 如果是纯问答任务（不需要分析文件），可以只有一步

请严格按以下JSON格式返回执行计划（不要加任何其他文字）：
{{
    "plan": [
        {{"step": 1, "tool": "工具名称", "args": {{"参数名": "参数值"}}, "reason": "为什么执行这一步"}},
        {{"step": 2, "tool": "工具名称", "args": {{"参数名": "参数值"}}, "reason": "为什么执行这一步"}}
    ]
}}"""


class TaskPlanner:
    """
    任务规划器：调用 LLM，根据用户任务和可用工具，自动生成执行计划。
    """

    def __init__(self):
        """初始化 LLM 客户端"""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        if not api_key:
            raise ValueError("❌ 未配置 DEEPSEEK_API_KEY，请检查 .env 文件")

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def create_plan(self, task: str, file_path: str = None) -> list:
        """
        根据用户任务，让 LLM 自主生成执行计划。
        
        参数：
        - task: 用户任务描述
        - file_path: （可选）如果有文件上传，传入文件路径
        
        返回值：
        计划步骤列表，如：
        [
            {"step": 1, "tool": "analyze_finance", "args": {"file_path": "xxx"}, "reason": "..."},
            {"step": 2, "tool": "generate_report", "args": {...}, "reason": "..."}
        ]
        """
        # 把文件路径信息注入到任务描述中
        enriched_task = task
        if file_path:
            enriched_task = f"{task}\n（财务数据文件路径：{file_path}）"

        # 填充提示词
        prompt = PLANNING_PROMPT.replace("{task}", enriched_task)

        print("🧠 正在让 LLM 自主规划执行步骤...")
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0  # 确保规划稳定
        )

        # 解析 LLM 返回的执行计划
        result_text = response.choices[0].message.content.strip()

        # 处理可能的代码块标记
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

        try:
            plan_data = json.loads(result_text)
            plan = plan_data.get("plan", [])
        except json.JSONDecodeError:
            print("⚠️ LLM 返回的规划无法解析，降级为默认流程")
            plan = self._default_plan(file_path)

        print(f"✅ LLM 已生成 {len(plan)} 步执行计划：")
        for step in plan:
            print(f"   第{step['step']}步：调用 {step['tool']}（原因：{step['reason']}）")

        return plan

    def _default_plan(self, file_path: str = None) -> list:
        """
        降级方案：如果 LLM 规划失败，使用默认流程。
        """
        if file_path:
            return [
                {"step": 1, "tool": "analyze_finance", "args": {"file_path": file_path}, "reason": "加载财务数据并执行合规检查"},
                {"step": 2, "tool": "generate_report", "args": {}, "reason": "生成最终报告"}
            ]
        else:
            return [
                {"step": 1, "tool": "search_law", "args": {"query": "用户问题"}, "reason": "检索相关法规"}
            ]


# ================================================================
# 测试代码
# ================================================================
if __name__ == "__main__":
    planner = TaskPlanner()

    # 测试：让 LLM 自己规划一个复杂任务
    print("=" * 60)
    print("测试：LLM 自主规划任务步骤")
    print("=" * 60)

    test_tasks = [
        "全面检查未来科技的税务合规情况，并生成报告。文件路径：data/sample/未来科技_2024Q3_财务数据.xlsx",
        "增值税申报期限是每月几号？",
    ]

    for task in test_tasks:
        print(f"\n📋 任务：{task}")
        plan = planner.create_plan(task)
        print()