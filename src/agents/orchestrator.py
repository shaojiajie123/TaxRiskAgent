"""
主控 Agent - 整合 LLM 自主规划 + 逐步执行
职责：接收用户任务 → 调 LLM 生成执行计划 → 逐步执行 → 汇总输出
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.tools.enhanced_analyzer import EnhancedFinanceAnalyzer
from src.rag.answer_generator import AnswerGenerator
from src.rag.hybrid_retriever import HybridRetriever
from src.agents.planner import TaskPlanner


class TaxRiskOrchestrator:
    """
    财税风险智能巡检主控 Agent
    
    核心升级：
    1. 引入 TaskPlanner，让 LLM 自主生成执行计划
    2. 按计划逐步执行，不再依赖硬编码流程
    3. 每步的输出自动传递给下一步
    """

    def __init__(self):
        """初始化主控 Agent，准备好所有工具箱"""
        print("🤖 主控 Agent 正在初始化...")
        
        # 任务规划器（LLM 自主规划）
        self.planner = TaskPlanner()
        
        # 工具箱
        self.answer_generator = AnswerGenerator()
        self.retriever = HybridRetriever(alpha=0.5)
        
        # 执行过程中的中间结果存储
        self.context = {}  # 用于在步骤之间传递数据
        
        print("✅ 主控 Agent 就绪")
        print("   可用工具：财务合规分析、法规检索、智能问答、AI建议生成、报告生成")

    # ================================================================
    # 核心方法：执行任务（升级版——LLM规划 + 逐步执行）
    # ================================================================
    def execute(self, task: str, file_path: str = None) -> dict:
        """
        执行用户给定的任务。
        1. 调 LLM 生成执行计划
        2. 逐步执行计划中的每一步
        3. 汇总输出
        """
        print(f"\n{'='*60}")
        print(f"📋 收到任务：{task}")
        print(f"{'='*60}")

        # ---- 第1步：让 LLM 自主规划 ----
        plan = self.planner.create_plan(task, file_path)
        
        if not plan:
            return {"error": "无法生成执行计划"}

        # ---- 第2步：逐步执行 ----
        print(f"\n⚡ 开始按计划逐步执行...")
        for step in plan:
            step_num = step["step"]
            tool_name = step["tool"]
            args = step.get("args", {})
            reason = step.get("reason", "无说明")
            
            print(f"\n📍 执行第{step_num}步：{tool_name}")
            print(f"   原因：{reason}")
            
            # 根据工具名称调用对应的工具
            result = self._execute_tool(tool_name, args)
            
            # 将结果存入上下文，供后续步骤使用
            self.context[f"step_{step_num}_result"] = result
            self.context["last_result"] = result
        
        # ---- 第3步：汇总输出 ----
        print(f"\n✅ 所有步骤执行完毕，正在汇总结果...")
        return self._aggregate_results(task, plan)

    # ================================================================
    # 工具执行调度器：根据工具名称调用对应的实际方法
    # ================================================================
    def _execute_tool(self, tool_name: str, args: dict):
        """根据LLM规划的工具名称，调用对应的实际方法"""
        
        if tool_name == "analyze_finance":
            return self._tool_analyze_finance(args)
        
        elif tool_name == "search_law":
            return self._tool_search_law(args)
        
        elif tool_name == "generate_advice":
            return self._tool_generate_advice(args)
        
        elif tool_name == "generate_report":
            return self._tool_generate_report(args)
        
        else:
            print(f"   ⚠️ 未知工具：{tool_name}，跳过")
            return {"error": f"未知工具：{tool_name}"}

    # ================================================================
    # 工具1：财务合规分析
    # ================================================================
    def _tool_analyze_finance(self, args: dict) -> dict:
        """执行财务合规分析"""
        file_path = args.get("file_path", "")
        
        if not file_path:
            # 尝试从上下文获取
            file_path = self.context.get("uploaded_file", "")
        
        if not file_path or not os.path.exists(file_path):
            return {"error": f"文件不存在：{file_path}"}
        
        analyzer = EnhancedFinanceAnalyzer(file_path)
        report = analyzer.run_full_enhanced_analysis()
        
        print(f"   ✅ 财务分析完成，发现 {report['summary']['total_risks']} 条风险")
        return report

    # ================================================================
    # 工具2：法规检索
    # ================================================================
    def _tool_search_law(self, args: dict) -> dict:
        """执行法规检索"""
        query = args.get("query", "")
        
        if not query:
            # 尝试从上下文中获取用户原始任务
            query = self.context.get("original_task", "税务合规")
        
        results = self.retriever.retrieve(query, top_k=3)
        
        laws = []
        for doc_content, score, meta in results:
            laws.append({
                "title": meta.get("title", "未知法规"),
                "score": round(score, 4),
                "content": doc_content[:300]
            })
        
        print(f"   ✅ 法规检索完成，找到 {len(laws)} 条相关法规")
        return {"query": query, "laws": laws}

    # ================================================================
    # 工具3：AI建议生成
    # ================================================================
    def _tool_generate_advice(self, args: dict) -> dict:
        """为风险项生成AI专业建议"""
        risk_info = args.get("risk_info", {})
        
        if not risk_info:
            # 尝试从上下文中获取上一步的风险列表
            last_result = self.context.get("last_result", {})
            risks = last_result.get("risks", [])
            if risks:
                risk_info = risks[0]  # 取第一条高风险作为示例
        
        if not risk_info:
            return {"error": "没有可用的风险信息"}
        
        query = f"{risk_info.get('check_name', '')} {risk_info.get('business', '')} 如何整改？"
        result = self.answer_generator.answer(query)
        
        print(f"   ✅ AI建议已生成")
        return {"risk": risk_info, "advice": result.get("answer", "")}

    # ================================================================
    # 工具4：报告生成
    # ================================================================
    def _tool_generate_report(self, args: dict) -> dict:
        """生成最终报告"""
        # 从上下文中收集所有步骤的结果
        analysis_result = self.context.get("step_1_result", {})
        search_result = self.context.get("step_2_result", {})
        advice_result = self.context.get("step_3_result", {})
        
        summary = analysis_result.get("summary", {})
        risks = analysis_result.get("risks", [])
        
        print(f"   ✅ 最终报告已生成")
        return {
            "summary": summary,
            "total_risks": len(risks),
            "risks": risks,
            "laws_found": search_result.get("laws", []),
            "ai_advice_sample": advice_result.get("advice", "")
        }

    # ================================================================
    # 汇总方法：将所有步骤的结果整合为最终输出
    # ================================================================
    def _aggregate_results(self, task: str, plan: list) -> dict:
        """汇总所有步骤的执行结果"""
        last_result = self.context.get("last_result", {})
        
        # 如果是简单问答，直接返回答案
        if len(plan) == 1 and plan[0]["tool"] == "search_law":
            laws = last_result.get("laws", [])
            return {
                "task": task,
                "intent": "问答",
                "plan": plan,
                "laws": laws
            }
        
        # 如果是复杂分析，返回完整报告
        return {
            "task": task,
            "intent": "全面检查",
            "plan": plan,
            "report": last_result
        }


# ================================================================
# 测试代码
# ================================================================
if __name__ == "__main__":
    agent = TaxRiskOrchestrator()

    # 测试：全面合规检查
    test_file = "data/sample/未来科技_2024Q3_财务数据.xlsx"
    if os.path.exists(test_file):
        result = agent.execute(
            task="全面检查未来科技2024年Q3的税务合规情况，并生成报告",
            file_path=test_file
        )
        
        print(f"\n{'='*60}")
        print(f"📋 最终输出")
        print(f"{'='*60}")
        
        if "report" in result:
            report = result["report"]
            summary = report.get("summary", {})
            print(f"审查记录：{summary.get('total_records', 0)} 条")
            print(f"发现风险：{report.get('total_risks', 0)} 条")
            print(f"执行计划：{len(result.get('plan', []))} 步")
        
        # 显示执行计划
        print(f"\n📝 LLM 生成的执行计划：")
        for step in result.get("plan", []):
            print(f"   第{step['step']}步：{step['tool']}（{step['reason']}）")