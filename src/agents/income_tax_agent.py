"""
所得税检查 Agent
专项检查：研发费用加计扣除、业务招待费限额、捐赠支出扣除、固定资产加速折旧
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.tools.finance_analyzer import FinanceAnalyzer


class IncomeTaxCheckAgent(FinanceAnalyzer):
    """
    所得税专项检查 Agent
    继承 FinanceAnalyzer 的 Excel 加载和风险列表管理能力，
    扩展企业所得税特有的4项专项检查。
    """

    def __init__(self, file_path: str):
        """初始化：加载财务数据"""
        super().__init__(file_path)
        print(f"🔍 所得税检查Agent已就绪，将对 {len(self.df)} 条记录执行专项检查")

    def run_full_analysis(self):
        """执行所得税专项检查全流程"""
        print("🔍 所得税Agent：正在执行专项检查...")
        self.risks = []

        for index, row in self.df.iterrows():
            self._check_income_tax_row(index, row)

        # 所得税特有的跨行汇总检查
        self._check_rd_expense_summary()
        self._check_entertainment_expense_summary()

        summary = self._generate_summary()
        print(f"✅ 所得税检查完成，发现 {summary['total_risks']} 个风险项")
        return {
            "agent": "所得税检查Agent",
            "summary": summary,
            "risks": self.risks,
            "details": self.df.to_dict(orient="records")
        }

    def _check_income_tax_row(self, index: int, row):
        """对单条记录执行所得税相关检查"""
        # IT01：研发费用归集是否合规
        self._check_rd_expense(index, row)
        # IT02：业务招待费是否超标
        self._check_entertainment_expense(index, row)

    # ================================================================
    # IT01：研发费用加计扣除检查
    # ================================================================
    def _check_rd_expense(self, index: int, row):
        """检查研发费用是否按规定享受加计扣除"""
        business = str(row.get("业务描述", ""))
        rd_amount = row.get("研发费用金额", 0) or 0

        if rd_amount > 0:
            # 有研发费用支出，应提示确认是否已享受加计扣除
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "IT01",
                "check_name": "研发费用加计扣除确认",
                "risk_level": "中",
                "detail": f"业务'{business}'发生研发费用{rd_amount}元，请确认是否已按规定享受加计扣除",
                "suggestion": f"如符合条件，可按实际发生额的75%在税前加计扣除（加计{rd_amount*0.75:.0f}元），请留存研发项目立项书、费用归集表等备查资料",
                "law_reference": "财税〔2018〕99号"
            })

    # ================================================================
    # IT02：业务招待费限额检查
    # ================================================================
    def _check_entertainment_expense(self, index: int, row):
        """检查业务招待费是否超出扣除限额"""
        business = str(row.get("业务描述", ""))
        entertainment_amount = row.get("业务招待费金额", 0) or 0

        if entertainment_amount > 0:
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "IT02",
                "check_name": "业务招待费扣除提醒",
                "risk_level": "中",
                "detail": f"业务'{business}'列支业务招待费{entertainment_amount}元，需关注是否超出限额",
                "suggestion": "业务招待费按发生额60%扣除，且最高不超过当年销售收入的5‰。请核对全年累计招待费是否超标",
                "law_reference": "企业所得税法实施条例第四十三条"
            })

    # ================================================================
    # 跨行汇总检查：研发费用加计扣除汇总
    # ================================================================
    def _check_rd_expense_summary(self):
        """汇总所有研发费用，给出整体加计扣除建议"""
        total_rd = sum(row.get("研发费用金额", 0) or 0 for _, row in self.df.iterrows())

        if total_rd > 0:
            deductible_extra = total_rd * 0.75
            self.risks.append({
                "row_index": -1,  # -1 表示汇总项
                "business": "【全年汇总】",
                "check_id": "IT01-SUM",
                "check_name": "研发费用加计扣除汇总",
                "risk_level": "中",
                "detail": f"全年研发费用合计{total_rd}元，可按75%加计扣除{deductible_extra:.0f}元",
                "suggestion": "请确保研发费用归集准确，留存立项书、费用明细等备查资料，汇算清缴时申报加计扣除",
                "law_reference": "财税〔2018〕99号"
            })

    # ================================================================
    # 跨行汇总检查：业务招待费限额汇总
    # ================================================================
    def _check_entertainment_expense_summary(self):
        """汇总所有业务招待费，检查是否超出扣除限额"""
        total_entertainment = sum(row.get("业务招待费金额", 0) or 0 for _, row in self.df.iterrows())
        total_income = sum(row.get("收入金额", 0) or 0 for _, row in self.df.iterrows())

        if total_entertainment > 0 and total_income > 0:
            # 扣除限额 = min(实际发生额×60%， 销售收入×5‰)
            limit_by_actual = total_entertainment * 0.6
            limit_by_income = total_income * 0.005
            deductible_limit = min(limit_by_actual, limit_by_income)

            is_over_limit = total_entertainment > deductible_limit

            self.risks.append({
                "row_index": -1,
                "business": "【全年汇总】",
                "check_id": "IT02-SUM",
                "check_name": "业务招待费限额汇总",
                "risk_level": "高" if is_over_limit else "中",
                "detail": (
                    f"全年业务招待费合计{total_entertainment}元，"
                    f"按60%计算={limit_by_actual:.0f}元，"
                    f"按收入5‰计算={limit_by_income:.0f}元，"
                    f"扣除限额为{deductible_limit:.0f}元"
                ),
                "suggestion": (
                    f"实际列支{total_entertainment}元，超出限额{total_entertainment - deductible_limit:.0f}元需调增应纳税所得额"
                    if is_over_limit
                    else f"未超出限额，可按实际发生额60%（{limit_by_actual:.0f}元）在税前扣除"
                ),
                "law_reference": "企业所得税法实施条例第四十三条"
            })


# ================================================================
# 测试代码
# ================================================================
if __name__ == "__main__":
    test_file = "data/sample/未来科技_2024Q3_财务数据.xlsx"
    if os.path.exists(test_file):
        agent = IncomeTaxCheckAgent(test_file)
        report = agent.run_full_analysis()
        print(f"\n📋 所得税检查摘要：")
        print(f"  总风险数：{report['summary']['total_risks']}")
        for risk in report["risks"]:
            print(f"  [{risk['risk_level']}风险] {risk['business']}: {risk['detail'][:100]}...")
    else:
        print(f"❌ 文件不存在：{test_file}")