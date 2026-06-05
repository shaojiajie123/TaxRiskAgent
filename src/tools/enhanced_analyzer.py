"""
增强版财务分析器
在 FinanceAnalyzer 的基础上，自动为每条风险检索对应的法规全文
"""
import os
import sys

# 将项目根目录加入系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.tools.finance_analyzer import FinanceAnalyzer  # 该模块能发现风险，但引用的只是文号，没有法规全文
from src.rag.hybrid_retriever import HybridRetriever    # 该模块能根据查询去检索法规全文，但它本身不知道该何时进行检索


class EnhancedFinanceAnalyzer(FinanceAnalyzer): # 继承父类FinanceAnalyzer 结合FinanceAnalyzer and HybridRetriever 返回的风险列表中包含法规全文 而不仅仅是法规文号
    """
    继承 FinanceAnalyzer 的全部检查能力，
    并增加“自动为风险检索法规原文”的能力。
    """

    def __init__(self, file_path: str):  # self.属性即时实例属性，每个实例特有的属性，相互独立，互不干扰
        """
        初始化：先调父类加载Excel，再初始化检索器。
        """
        # 调用父类 __init__，完成Excel加载等初始化工作
        super().__init__(file_path)

        # 初始化混合检索器，用于查找法规全文
        print("🔧 正在初始化法规检索器...")
        self.retriever = HybridRetriever(alpha=0.5)     # self.retriever = 我这个实例的检索器 相比于父类的风险分析器，该分析器在初始化时多添加了混合检索功能
        print("   法规检索器就绪")

    # ================================================================
    # 核心增强：为风险列表逐条检索法规全文
    # ================================================================
    def enrich_risks_with_law_details(self) -> list:
        """
        遍历所有已发现的风险，为每条风险检索对应的法规全文。
        
        返回值：增强后的风险列表，每条风险新增 law_full_text 字段。
        """
        if not self.risks:
            print("   没有风险项需要增强")
            return self.risks

        print(f"📚 正在为 {len(self.risks)} 条风险检索法规全文...")

        enriched_risks = []
        for i, risk in enumerate(self.risks):
            # 构造检索查询：用风险描述 + 法律依据文号
            query = f"{risk['check_name']} {risk['business']} {risk['law_reference']}"
            
            # 用混合检索器去知识库找最相关的法规
            results = self.retriever.retrieve(query, top_k=3)

            # 提取检索到的法规全文（取第一条结果）
            if results:
                law_full_text = results[0][0]  # results[0] = (文本, 得分, 元数据)
                law_title = results[0][2].get("title", "未知法规")
                law_score = results[0][1]
            else:
                law_full_text = "未在知识库中找到对应法规全文"
                law_title = "未知"
                law_score = 0.0

            # 把法规全文追加到原风险字典中
            enriched_risk = risk.copy()
            enriched_risk["law_full_text"] = law_full_text
            enriched_risk["law_title"] = law_title
            enriched_risk["law_retrieval_score"] = round(law_score, 4)
            enriched_risks.append(enriched_risk)

            print(f"   [{i+1}/{len(self.risks)}] {risk['check_name']} → {law_title} (得分: {law_score:.4f})")

        # 用增强后的风险列表替换原始列表
        self.risks = enriched_risks
        print(f"✅ 法规全文检索完成")
        return self.risks

    # ================================================================
    # 一站式方法：分析 + 增强 + 生成报告
    # ================================================================
    def run_full_enhanced_analysis(self) -> dict:
        """
        执行完整流程：合规检查 → 法规全文检索 → 生成汇总报告。
        这是外部调用的唯一入口。
        """
        # 第1步：执行合规检查（继承自父类的方法）
        base_report = self.run_full_analysis()

        # 第2步：为风险检索法规全文
        self.enrich_risks_with_law_details()

        # 第3步：生成增强版汇总报告
        summary = self._generate_summary()

        print(f"\n✅ 增强分析完成，发现 {summary['total_risks']} 个风险项")
        return {
            "summary": summary,
            "risks": self.risks,
            "details": self.df.to_dict(orient="records")
        }


# ================================================================
# 测试代码
# ================================================================
if __name__ == "__main__":
    test_file = "data/sample/未来科技_2024Q3_财务数据.xlsx"

    if not os.path.exists(test_file):
        print(f"❌ 测试文件不存在：{test_file}")
        print("   请先运行 scripts/generate_sample_data.py 生成数据")
    else:
        # 使用增强版分析器
        analyzer = EnhancedFinanceAnalyzer(test_file)
        report = analyzer.run_full_enhanced_analysis()

        print("\n" + "=" * 60)
        print("📋 增强分析报告摘要")
        print("=" * 60)
        summary = report["summary"]
        print(f"总记录数：{summary['total_records']}")
        print(f"风险总数：{summary['total_risks']}")
        print(f"  · 高风险：{summary['high_risk_count']}")
        print(f"  · 中风险：{summary['mid_risk_count']}")

        print("\n🔴 风险详情（前3条，含法规全文）：")
        for risk in report["risks"][:3]:
            print(f"\n  [{risk['risk_level']}风险] {risk['business']}")
            print(f"  问题：{risk['detail']}")
            print(f"  依据：{risk['law_reference']}")
            print(f"  匹配法规：{risk.get('law_title', '未知')}")
            print(f"  法规全文预览：{risk.get('law_full_text', '无')[:120]}...")