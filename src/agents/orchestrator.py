"""
主控 Agent - 任务编排与调度
职责：接收用户任务 → 分解步骤 → 调度工具模块 → 汇总输出
"""
import os
import sys

# 将项目根目录加入系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.tools.enhanced_analyzer import EnhancedFinanceAnalyzer
from src.rag.answer_generator import AnswerGenerator


class TaxRiskOrchestrator:
    """
    财税风险智能巡检主控 Agent
    
    核心能力：
    1. 接收自然语言任务指令
    2. 自动分解为子任务
    3. 调度已有工具模块（分析、检索、生成）
    4. 汇总结果，输出结构化报告
    """

    def __init__(self):
        """初始化主控 Agent，准备好所有工具箱"""
        print("🤖 主控 Agent 正在初始化...")
        
        # 问答生成器（内部已包含意图分类 + 混合检索）
        self.answer_generator = AnswerGenerator()
        
        # 财务分析器留到执行时再初始化（因为需要指定文件路径）
        self.analyzer = None
        
        print("✅ 主控 Agent 就绪")
        print("   可用工具：财务合规分析、法规检索、智能问答、报告生成")

    # ================================================================
    # 核心方法：执行任务
    # ================================================================
    def execute(self, task: str, file_path: str = None) -> dict:
        """
        执行用户给定的任务。
        
        参数：
        - task: 用户的任务描述，如 "全面检查未来科技的税务合规情况"
        - file_path: （可选）财务数据文件的路径
        
        返回值：
        结构化报告字典，包含任务摘要、分析结果、法规依据等
        """
        print(f"\n{'='*60}")
        print(f"📋 收到任务：{task}")
        print(f"{'='*60}")

        # ---- 第1步：解析任务意图 ----
        intent = self._parse_task_intent(task)
        print(f"🔍 识别任务意图：{intent}")

        # ---- 第2步：根据意图选择执行路径 ----
        if intent == "全面检查" and file_path:
            return self._run_full_inspection(task, file_path)
        elif intent == "问答":
            return self._run_qa(task)
        else:
            return self._run_qa(task)  # 默认走问答

    # ================================================================
    # 任务意图解析（简单规则版，后续可升级为LLM判断）
    # ================================================================
    def _parse_task_intent(self, task: str) -> str:
        """
        解析用户任务的意图类型。
        当前使用关键词匹配，后续可替换为 LLM 判断。
        """
        keywords_inspect = ["检查", "合规", "审计", "巡检", "风险", "排查", "全面"]
        keywords_qa = ["是什么", "多少", "几号", "规定", "政策", "怎么", "如何", "解释"]
        
        task_lower = task.lower()
        
        if any(kw in task_lower for kw in keywords_inspect):
            return "全面检查"
        elif any(kw in task_lower for kw in keywords_qa):
            return "问答"
        else:
            return "问答"

    # ================================================================
    # 执行路径A：全面合规检查
    # ================================================================
    def _run_full_inspection(self, task: str, file_path: str) -> dict:
        """
        执行全面合规检查流程：
        加载财务数据 → 逐行检查 → 检索法规原文 → 生成报告
        """
        print(f"\n📊 启动全面合规检查流程...")
        print(f"   数据文件：{file_path}")

        # ---- 子任务A：初始化财务分析器 ----
        print("\n🔍 子任务A：加载财务数据...")
        if not os.path.exists(file_path):
            return {"error": f"文件不存在：{file_path}"}
        
        self.analyzer = EnhancedFinanceAnalyzer(file_path)
        
        # ---- 子任务B：执行合规检查 ----
        print("\n🔍 子任务B：执行合规检查...")
        report = self.analyzer.run_full_enhanced_analysis()
        
        # ---- 子任务C：为每条高风险项生成专业建议 ----
        print("\n🔍 子任务C：为高风险项生成专业建议...")
        high_risks = [r for r in report["risks"] if r["risk_level"] == "高"]
        
        for i, risk in enumerate(high_risks[:5]):  # 最多处理5条高风险
            query = f"{risk['check_name']} {risk['business']} 如何整改？依据是什么？"
            try:
                advice = self.answer_generator.answer(query)
                risk["ai_advice"] = advice.get("answer", "无法生成建议")
            except Exception as e:
                risk["ai_advice"] = f"生成建议时出错：{e}"
            print(f"   [{i+1}/{len(high_risks[:5])}] {risk['business']} → 建议已生成")
        
        # ---- 子任务D：生成最终摘要 ----
        print("\n🔍 子任务D：生成最终摘要...")
        summary = self._generate_executive_summary(report, task)
        
        print(f"\n✅ 全面检查完成！")
        return {
            "task": task,
            "intent": "全面检查",
            "summary": summary,
            "report": report
        }

    # ================================================================
    # 执行路径B：智能问答
    # ================================================================
    def _run_qa(self, task: str) -> dict:
        """
        执行智能问答流程：意图分类 → 检索法规 → 生成回答
        """
        print(f"\n💬 启动智能问答流程...")
        result = self.answer_generator.answer(task)
        print(f"✅ 问答完成")
        return {
            "task": task,
            "intent": "问答",
            "intent_type": result["intent"],
            "answer": result["answer"],
            "references": [
                {"title": doc[2].get("title", "未知"), "score": doc[1]}
                for doc in result["documents"]
            ]
        }

    # ================================================================
    # 辅助方法：生成执行摘要
    # ================================================================
    def _generate_executive_summary(self, report: dict, task: str) -> str:
        """
        根据分析报告，生成一段可读的执行摘要。
        """
        summary_data = report.get("summary", {})
        total_risks = summary_data.get("total_risks", 0)
        high_risks = summary_data.get("high_risk_count", 0)
        mid_risks = summary_data.get("mid_risk_count", 0)
        total_records = summary_data.get("total_records", 0)
        
        # 按类别统计
        categories = summary_data.get("risk_categories", {})
        cat_details = "、".join([f"{k}{v}条" for k, v in categories.items() if v > 0])
        
        summary = (
            f"对「{task}」的全面检查已完成。"
            f"共审查 {total_records} 条财务记录，"
            f"发现 {total_risks} 个风险项"
            f"（高风险 {high_risks} 项、中风险 {mid_risks} 项）。"
            f"主要问题集中在：{cat_details}。"
            f"详细风险清单及整改建议请见完整报告。"
        )
        
        return summary


# ================================================================
# 测试代码：运行此文件可直接体验 Agent 调度效果
# ================================================================
if __name__ == "__main__":
    # 初始化主控 Agent
    agent = TaxRiskOrchestrator()

    # 测试场景1：全面合规检查
    test_file = "data/sample/未来科技_2024Q3_财务数据.xlsx"
    if os.path.exists(test_file):
        result = agent.execute(
            task="全面检查未来科技2024年Q3的税务合规情况",
            file_path=test_file
        )
        
        print(f"\n{'='*60}")
        print(f"📋 最终报告摘要")
        print(f"{'='*60}")
        print(result.get("summary", "无摘要"))
        
        # 展示前3条高风险详情
        if "report" in result:
            high_risks = [r for r in result["report"]["risks"] if r["risk_level"] == "高"]
            print(f"\n🔴 高风险项详情（前3条）：")
            for risk in high_risks[:3]:
                print(f"\n  · {risk['business']}")
                print(f"    问题：{risk['detail']}")
                print(f"    依据：{risk['law_reference']}")
                print(f"    法规原文：{risk.get('law_full_text', '无')[:100]}...")
                if "ai_advice" in risk:
                    print(f"    AI建议：{risk['ai_advice'][:150]}...")

    # 测试场景2：智能问答
    print(f"\n{'='*60}")
    print(f"📋 智能问答测试")
    print(f"{'='*60}")
    qa_result = agent.execute(task="增值税申报期限是每月几号？")
    print(f"\n回答：{qa_result.get('answer', '无回答')[:200]}...")