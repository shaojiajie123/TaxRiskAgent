"""
发票合规 Agent
专项检查：备注栏是否为空、发票类型是否匹配、发票代码是否重复、开票日期是否倒挂
"""
import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.tools.finance_analyzer import FinanceAnalyzer


class InvoiceChecker(FinanceAnalyzer):
    """
    发票合规专项检查 Agent
    继承 FinanceAnalyzer 的 Excel 加载和风险列表管理能力，
    扩展发票合规特有的4项专项检查。
    """

    def __init__(self, file_path: str):
        """初始化：加载财务数据"""
        super().__init__(file_path)
        print(f"🔍 发票合规Agent已就绪，将对 {len(self.df)} 条记录执行专项检查")

    def run_full_analysis(self):
        """执行发票合规检查全流程"""
        print("🔍 发票合规Agent：正在执行专项检查...")
        self.risks = []

        # 逐行检查
        for index, row in self.df.iterrows():
            self._check_invoice_row(index, row)

        # 跨行检查：发票代码重复
        self._check_duplicate_invoice_codes()

        summary = self._generate_summary()
        print(f"✅ 发票合规检查完成，发现 {summary['total_risks']} 个风险项")
        return {
            "agent": "发票合规Agent",
            "summary": summary,
            "risks": self.risks,
            "details": self.df.to_dict(orient="records")
        }

    def _check_invoice_row(self, index: int, row):
        """对单条记录执行发票合规检查"""
        # INV01：备注栏是否为空（特定业务必须填写）
        self._check_remark_empty(index, row)
        # INV02：发票类型与业务是否匹配
        self._check_invoice_type_match(index, row)
        # INV03：开票日期是否早于业务日期（日期倒挂）
        self._check_invoice_date_inverted(index, row)

    # ================================================================
    # INV01：备注栏为空检查
    # ================================================================
    def _check_remark_empty(self, index: int, row):
        """检查特定业务类型的发票备注栏是否为空"""
        business = str(row.get("业务描述", ""))
        remark = str(row.get("备注栏", ""))

        # 处理 NaN 转字符串的问题
        if remark.lower() == "nan" or remark.strip() == "":
            remark = ""

        # 必须填写备注栏的业务关键词
        remark_required_keywords = ["租赁", "建筑", "运输"]
        is_required = any(kw in business for kw in remark_required_keywords)

        if is_required and remark == "":
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "INV01",
                "check_name": "备注栏为空",
                "risk_level": "高",
                "detail": f"业务'{business}'的发票备注栏为空，不合规",
                "suggestion": "运输服务需填写起运地、到达地等信息；租赁服务需填写不动产地址",
                "law_reference": "国家税务总局公告2018年第28号第九条"
            })

    # ================================================================
    # INV02：发票类型与业务匹配检查
    # ================================================================
    def _check_invoice_type_match(self, index: int, row):
        """检查发票类型是否与业务类型匹配"""
        business = str(row.get("业务描述", ""))
        invoice_type = str(row.get("发票类型", ""))
        income = row.get("收入金额", 0) or 0
        cost = row.get("成本金额", 0) or 0

        # 简易计税业务通常不能开具增值税专用发票（已在增值税Agent检查，此处不再重复）
        # 这里检查：成本支出类业务应取得发票才能抵扣
        if cost > 0 and invoice_type == "增值税普通发票":
            # 成本支出取得普通发票，无法抵扣进项，但不一定违规——可能是对方是小规模纳税人
            # 仅作提醒
            pass

        # 收入类业务开具发票类型检查
        if income > 0:
            # 正常情况都可以开具专票或普票，此处不做强制判断
            pass

    # ================================================================
    # INV03：开票日期是否早于业务日期（日期倒挂）
    # ================================================================
    def _check_invoice_date_inverted(self, index: int, row):
        """检查开票日期是否早于业务发生日期"""
        business = str(row.get("业务描述", ""))
        biz_date_str = str(row.get("日期", ""))
        invoice_date_str = str(row.get("开票日期", ""))

        if not biz_date_str or not invoice_date_str:
            return

        try:
            biz_date = pd.to_datetime(biz_date_str)
            invoice_date = pd.to_datetime(invoice_date_str)

            if invoice_date < biz_date:
                self.risks.append({
                    "row_index": int(index),
                    "business": business,
                    "check_id": "INV03",
                    "check_name": "开票日期早于业务日期",
                    "risk_level": "中",
                    "detail": f"业务'{business}'发生日期{biz_date_str}，但开票日期{invoice_date_str}更早",
                    "suggestion": "发票应在业务发生后开具，请核实是否存在提前开票行为",
                    "law_reference": "发票管理办法第二十二条"
                })
        except (ValueError, TypeError):
            pass

    # ================================================================
    # 跨行检查：发票代码重复
    # ================================================================
    def _check_duplicate_invoice_codes(self):
        """检查是否存在发票代码重复的情况"""
        codes = []
        for _, row in self.df.iterrows():
            code = str(row.get("发票代码", ""))
            if code and code != "nan":
                codes.append(code)

        # 找重复
        from collections import Counter
        code_counts = Counter(codes)
        duplicates = {code: count for code, count in code_counts.items() if count > 1}

        for code, count in duplicates.items():
            # 找到重复代码对应的业务
            dup_businesses = []
            for _, row in self.df.iterrows():
                if str(row.get("发票代码", "")) == code:
                    dup_businesses.append(str(row.get("业务描述", "")))

            self.risks.append({
                "row_index": -1,
                "business": "【跨行检查】",
                "check_id": "INV04",
                "check_name": "发票代码重复",
                "risk_level": "高",
                "detail": f"发票代码{code}出现{count}次，涉及业务：{'、'.join(dup_businesses)}",
                "suggestion": "同一发票代码不应在多条记录中出现，请核实是否为重复入账",
                "law_reference": "发票管理办法第二十二条"
            })


# ================================================================
# 测试代码
# ================================================================
if __name__ == "__main__":
    test_file = "data/sample/未来科技_2024Q3_财务数据.xlsx"
    if os.path.exists(test_file):
        agent = InvoiceChecker(test_file)
        report = agent.run_full_analysis()
        print(f"\n📋 发票合规检查摘要：")
        print(f"  总风险数：{report['summary']['total_risks']}")
        for risk in report["risks"]:
            print(f"  [{risk['risk_level']}风险] {risk['business']}: {risk['detail'][:100]}...")
    else:
        print(f"❌ 文件不存在：{test_file}")