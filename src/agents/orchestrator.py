"""
主控 Agent - 整合 LLM 自主规划 + 多Agent并行协作
职责：接收用户任务 → 调 LLM 生成执行计划 → 并行调度子Agent → 汇总输出
"""
import os
import sys
import concurrent.futures

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.rag.answer_generator import AnswerGenerator
from src.rag.hybrid_retriever import HybridRetriever
from src.agents.planner import TaskPlanner
from src.agents.vat_checker import VATChecker
from src.agents.income_tax_checker import IncomeTaxChecker
from src.agents.invoice_checker import InvoiceChecker


class TaxRiskOrchestrator:
    """
    财税风险智能巡检主控 Agent

    核心升级：
    1. TaskPlanner：LLM 自主生成执行计划
    2. 多Agent并行：增值税/所得税/发票合规三个Agent同时检查
    3. 结果汇总：自动合并三个Agent的风险列表
    """

    def __init__(self):
        """初始化主控 Agent"""
        print("🤖 主控 Agent 正在初始化...")
        self.planner = TaskPlanner()
        self.answer_generator = AnswerGenerator()
        self.retriever = HybridRetriever(alpha=0.5)
        self.context = {}
        print("✅ 主控 Agent 就绪")
        print("   可用子Agent：增值税检查、所得税检查、发票合规检查")

    # ================================================================
    # 核心方法：执行任务
    # ================================================================
    def execute(self, task: str, file_path: str = None) -> dict:
        """执行用户任务：先规划，再执行，最后汇总"""
        print(f"\n{'='*60}")
        print(f"📋 收到任务：{task}")
        print(f"{'='*60}")

        plan = self.planner.create_plan(task, file_path)
        if not plan:
            return {"error": "无法生成执行计划"}

        print(f"\n⚡ 开始按计划逐步执行...")
        for step in plan:
            step_num = step["step"]
            tool_name = step["tool"]
            args = step.get("args", {})
            reason = step.get("reason", "无说明")

            print(f"\n📍 执行第{step_num}步：{tool_name}")
            print(f"   原因：{reason}")

            result = self._execute_tool(tool_name, args)
            self.context[f"step_{step_num}_result"] = result
            self.context["last_result"] = result

        print(f"\n✅ 所有步骤执行完毕，正在汇总...")
        return self._aggregate_results(task, plan)

    # ================================================================
    # 工具执行调度器
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
    # 工具1：财务合规分析（升级版——三Agent并行）
    # ================================================================
    def _tool_analyze_finance(self, args: dict) -> dict:
        """
        并行启动增值税、所得税、发票合规三个专项Agent，
        各自独立检查，最后汇总结果。
        """
        file_path = args.get("file_path", "")
        if not file_path:
            file_path = self.context.get("uploaded_file", "")
        if not file_path or not os.path.exists(file_path):
            return {"error": f"文件不存在：{file_path}"}

        print(f"🚀 正在并行启动三个专项检查Agent...")

        # 定义三个Agent的创建函数
        def run_vat():
            print("   🔍 增值税Agent 启动...")
            agent = VATChecker(file_path)
            return agent.run_full_analysis()

        def run_income_tax():
            print("   🔍 所得税Agent 启动...")
            agent = IncomeTaxChecker(file_path)
            return agent.run_full_analysis()

        def run_invoice():
            print("   🔍 发票合规Agent 启动...")
            agent = InvoiceChecker(file_path)
            return agent.run_full_analysis()

        # 使用线程池并行执行三个Agent
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_vat = executor.submit(run_vat)
            future_income_tax = executor.submit(run_income_tax)
            future_invoice = executor.submit(run_invoice)

            # 等待全部完成
            vat_report = future_vat.result()
            income_tax_report = future_income_tax.result()
            invoice_report = future_invoice.result()

        # 汇总三个Agent的结果
        all_risks = (
            vat_report.get("risks", []) +
            income_tax_report.get("risks", []) +
            invoice_report.get("risks", [])
        )

        total_records = len(vat_report.get("details", []))

        # 统计汇总
        high_risks = [r for r in all_risks if r.get("risk_level") == "高"]
        mid_risks = [r for r in all_risks if r.get("risk_level") == "中"]

        summary = {
            "total_records": total_records,
            "total_risks": len(all_risks),
            "high_risk_count": len(high_risks),
            "mid_risk_count": len(mid_risks),
            "risk_categories": {
                "增值税问题": vat_report["summary"]["total_risks"],
                "所得税问题": income_tax_report["summary"]["total_risks"],
                "发票合规问题": invoice_report["summary"]["total_risks"],
            },
            "agents": {
                "vat": vat_report["summary"],
                "income_tax": income_tax_report["summary"],
                "invoice": invoice_report["summary"]
            }
        }

        print(f"\n✅ 三Agent并行检查完成：")
        print(f"   增值税Agent：{vat_report['summary']['total_risks']} 条风险")
        print(f"   所得税Agent：{income_tax_report['summary']['total_risks']} 条风险")
        print(f"   发票合规Agent：{invoice_report['summary']['total_risks']} 条风险")
        print(f"   合计：{len(all_risks)} 条风险")

        return {
            "summary": summary,
            "risks": all_risks,
            "details": vat_report.get("details", [])
        }

    # ================================================================
    # 工具2：法规检索
    # ================================================================
    def _tool_search_law(self, args: dict) -> dict:
        query = args.get("query", self.context.get("original_task", "税务合规"))
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
        """
        为第一步发现的高风险项逐条生成 AI 建议，
        并直接回填到 step_1_result['risks'] 中。
        """
        # 1. 取第一步的分析结果
        analysis_result = self.context.get("step_1_result", {})
        risks = analysis_result.get("risks", [])
        high_risks = [r for r in risks if r.get("risk_level") == "高"]

        if not high_risks:
            print("   没有高风险项，跳过 AI 建议生成")
            return {"advised": 0}

        print(f"   正在为 {len(high_risks)} 条高风险项生成 AI 建议...")

        for i, risk in enumerate(high_risks):
            business = risk.get("business", "")
            check_name = risk.get("check_name", "")
            law_ref = risk.get("law_reference", "")

            # 构造查询
            query = f"业务'{business}'存在'{check_name}'问题，依据{law_ref}，请给出整改建议"
            try:
                result = self.answer_generator.answer(query)
                advice_text = result.get("answer", "")
                # 取第一个引用法规的全文
                docs = result.get("documents", [])
                if docs:
                    law_full = docs[0][0][:500]
                    law_title = docs[0][2].get("title", "未知法规")
                else:
                    law_full = ""
                    law_title = ""

                # ★ 关键：直接修改 risk 字典（它是 risks 列表里那个字典的引用）
                risk["ai_advice"] = advice_text
                risk["law_full_text"] = law_full
                risk["law_title"] = law_title

                print(f"   [{i+1}/{len(high_risks)}] {business} → 建议已生成并回填")
            except Exception as e:
                print(f"   [{i+1}/{len(high_risks)}] {business} → 生成失败：{e}")
                risk["ai_advice"] = f"生成建议时出错：{e}"

        # 2. 更新上下文
        self.context["step_1_result"] = analysis_result
        self.context["last_result"] = analysis_result

        print(f"   ✅ AI建议生成并回填完成，共处理 {len(high_risks)} 条")
        return {"advised": len(high_risks)}

    # ================================================================
    # 工具4：报告生成
    # ================================================================
    def _tool_generate_report(self, args: dict) -> dict:
        analysis_result = self.context.get("step_1_result", {})
        summary = analysis_result.get("summary", {})
        risks = analysis_result.get("risks", [])
        print(f"   ✅ 最终报告已生成")
        return {
            "summary": summary,
            "total_risks": len(risks),
            "risks": risks,
        }

    # ================================================================
    # 汇总方法
    # ================================================================
    def _aggregate_results(self, task: str, plan: list) -> dict:
        last_result = self.context.get("last_result", {})

        # 问答路径：调用 AnswerGenerator 生成完整回答
        if len(plan) == 1 and plan[0]["tool"] == "search_law":
            laws = last_result.get("laws", [])
            try:
                qa_result = self.answer_generator.answer(task)
                answer = qa_result.get("answer", "无法生成回答")
                references = [
                    {"title": doc[2].get("title", "未知"), "score": doc[1]}
                    for doc in qa_result.get("documents", [])
                ]
            except Exception:
                answer = "无法生成回答"
                references = []
            return {
                "task": task,
                "intent": "问答",
                "plan": plan,
                "answer": answer,
                "references": references,
                "laws": laws
            }

        # 全面检查路径
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
            print(f"  🔴 高风险：{summary.get('high_risk_count', 0)} 条")
            print(f"  🟡 中风险：{summary.get('mid_risk_count', 0)} 条")

            # 按Agent分别展示
            agents_info = summary.get("agents", {})
            for agent_name, agent_summary in agents_info.items():
                label = {"vat": "增值税", "income_tax": "所得税", "invoice": "发票合规"}.get(agent_name, agent_name)
                print(f"  · {label}Agent：{agent_summary.get('total_risks', 0)} 条")

        print(f"\n📝 LLM 生成的执行计划：")
        for step in result.get("plan", []):
            print(f"   第{step['step']}步：{step['tool']}（{step['reason']}）")
    else:
        print(f"❌ 文件不存在：{test_file}")