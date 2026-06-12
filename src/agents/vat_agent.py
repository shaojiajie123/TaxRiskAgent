"""
增值税检查 Agent
专项检查：销进项匹配、税率正确性、计税方式合规、加计抵减应享未享
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.tools.finance_analyzer import FinanceAnalyzer


class VATCheckAgent(FinanceAnalyzer):
    """
    增值税专项检查 Agent
    继承 FinanceAnalyzer 的 Excel 加载和风险列表管理能力，
    扩展增值税特有的4项专项检查。
    """

    def __init__(self, file_path: str):
        """初始化：加载财务数据"""
        super().__init__(file_path)
        print(f"🔍 增值税检查Agent已就绪，将对 {len(self.df)} 条记录执行专项检查")

    def run_full_analysis(self):
        """执行增值税专项检查全流程"""
        print("🔍 增值税Agent：正在执行专项检查...")
        self.risks = []

        for index, row in self.df.iterrows():
            self._check_vat_row(index, row)

        summary = self._generate_summary()
        print(f"✅ 增值税检查完成，发现 {summary['total_risks']} 个风险项")
        return {
            "agent": "增值税检查Agent",
            "summary": summary,
            "risks": self.risks,
            "details": self.df.to_dict(orient="records")
        }

    def _check_vat_row(self, index: int, row):
        """对单条记录执行全部增值税检查"""
        # VA01：销项税额与收入×税率是否匹配
        self._check_vat_output_tax(index, row)
        # VA02：进项税额与成本×税率是否匹配
        self._check_vat_input_tax(index, row)
        # VA03：简易计税与一般计税是否混用
        self._check_vat_method(index, row)
        # VA04：是否应享未享加计抵减
        self._check_vat_extra_deduction(index, row)

    # ================================================================
    # VA01：销项税额验算
    # ================================================================
    def _check_vat_output_tax(self, index: int, row):
        """验算销项税额 = 收入金额 × 适用税率"""
        business = str(row.get("业务描述", ""))
        income = row.get("收入金额", 0) or 0
        output_tax = row.get("销项税额", 0) or 0
        rate_str = str(row.get("适用税率", "0%"))

        if income == 0:
            return

        try:
            rate = float(rate_str.replace("%", "")) / 100
        except ValueError:
            return

        expected_tax = round(income * rate, 2)
        actual_tax = round(output_tax, 2)

        if abs(expected_tax - actual_tax) > 0.05:
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "VA01",
                "check_name": "销项税额计算错误",
                "risk_level": "高",
                "detail": f"收入{income}×税率{rate_str}，应缴{expected_tax}，实际{actual_tax}，差异{round(abs(expected_tax-actual_tax),2)}",
                "suggestion": "请核实销项税额计算，确保按适用税率准确计提",
                "law_reference": "财税〔2016〕36号第十五条、第二十五条"
            })

    # ================================================================
    # VA02：进项税额验算
    # ================================================================
    def _check_vat_input_tax(self, index: int, row):
        """验算进项税额 = 成本金额 × 适用税率"""
        business = str(row.get("业务描述", ""))
        cost = row.get("成本金额", 0) or 0
        input_tax = row.get("进项税额", 0) or 0
        rate_str = str(row.get("适用税率", "0%"))

        if cost == 0:
            return

        try:
            rate = float(rate_str.replace("%", "")) / 100
        except ValueError:
            return

        expected_tax = round(cost * rate, 2)
        actual_tax = round(input_tax, 2)

        if abs(expected_tax - actual_tax) > 0.05:
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "VA02",
                "check_name": "进项税额计算错误",
                "risk_level": "高",
                "detail": f"成本{cost}×税率{rate_str}，应抵{expected_tax}，实际{actual_tax}，差异{round(abs(expected_tax-actual_tax),2)}",
                "suggestion": "请核实进项税额计算，确保取得合规抵扣凭证",
                "law_reference": "财税〔2016〕36号第二十五条"
            })

    # ================================================================
    # VA03：计税方式检查
    # ================================================================
    def _check_vat_method(self, index: int, row):
        """检查简易计税与一般计税是否混用"""
        business = str(row.get("业务描述", ""))
        method = str(row.get("计税方式", ""))
        income = row.get("收入金额", 0) or 0
        input_tax = row.get("进项税额", 0) or 0

        # 简易计税项目不能抵扣进项
        if method == "简易计税" and input_tax > 0:
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "VA03",
                "check_name": "简易计税抵扣进项",
                "risk_level": "高",
                "detail": f"业务'{business}'采用简易计税，但申报了进项税额{input_tax}元",
                "suggestion": "简易计税项目不得抵扣进项税额，应做进项税额转出",
                "law_reference": "财税〔2016〕36号附件1第十八条"
            })

        # 简易计税不能开具增值税专用发票（特定情况除外）
        if method == "简易计税" and income > 0:
            invoice_type = str(row.get("发票类型", ""))
            if "专用发票" in invoice_type:
                self.risks.append({
                    "row_index": int(index),
                    "business": business,
                    "check_id": "VA03",
                    "check_name": "简易计税开具专票",
                    "risk_level": "中",
                    "detail": f"业务'{business}'采用简易计税，但开具了增值税专用发票",
                    "suggestion": "简易计税通常只能开具增值税普通发票，请确认是否符合开具专票的特殊条件",
                    "law_reference": "国家税务总局公告2016年第23号"
                })

    # ================================================================
    # VA04：加计抵减应享未享检查
    # ================================================================
    def _check_vat_extra_deduction(self, index: int, row):
        """检查生产、生活性服务业纳税人是否应享未享加计抵减"""
        business = str(row.get("业务描述", ""))
        is_enjoyed = str(row.get("是否享受加计抵减", "否"))
        input_tax = row.get("进项税额", 0) or 0

        # 属于生产、生活性服务业的业务类型
        service_keywords = ["咨询", "开发", "设计", "运维", "转让", "策划", "法律", "审计", "推广", "广告"]

        if any(kw in business for kw in service_keywords) and input_tax > 0:
            if is_enjoyed == "否":
                self.risks.append({
                    "row_index": int(index),
                    "business": business,
                    "check_id": "VA04",
                    "check_name": "加计抵减应享未享",
                    "risk_level": "中",
                    "detail": f"业务'{business}'属于生产/生活性服务业，有可抵扣进项{input_tax}元，但未享受加计抵减政策",
                    "suggestion": "建议申请享受加计抵减政策，按当期可抵扣进项税额加计10%抵减应纳税额",
                    "law_reference": "国家税务总局公告2019年第39号第七条"
                })


# ================================================================
# 测试代码
# ================================================================
if __name__ == "__main__":
    test_file = "data/sample/未来科技_2024Q3_财务数据.xlsx"
    if os.path.exists(test_file):
        agent = VATCheckAgent(test_file)
        report = agent.run_full_analysis()
        print(f"\n📋 增值税检查摘要：")
        print(f"  总风险数：{report['summary']['total_risks']}")
        for risk in report["risks"]:
            print(f"  [{risk['risk_level']}风险] {risk['business']}: {risk['detail'][:80]}...")
    else:
        print(f"❌ 文件不存在：{test_file}")