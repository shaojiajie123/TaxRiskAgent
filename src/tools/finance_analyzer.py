"""
财务数据分析工具
负责：读取财务Excel → 逐项合规检查 → 生成结构化分析结果
"""
import pandas as pd
from typing import Dict, Any, List


class FinanceAnalyzer:
    """
    财税数据自动分析器
    能力：加载报表、税额验算、合规项检查、风险点标注
    """

    # ================================================================
    # 类属性 在初始化函数外面定义的属性 所有实例共用 在定义类的时候就加载到内存了
    # 业务规则库（硬编码的财税合规规则）
    # 在真实项目中，这些规则可能来自数据库或配置文件
    # ================================================================
    
    # 各业务类型对应的正确法定税率   发现模拟数据中的税率错误的依据就是这个字典
    TAX_RATE_MAP = {
        "咨询费收入": 0.06,
        "技术开发收入": 0.06,
        "广告设计服务": 0.06,
        "UI设计服务": 0.06,
        "系统运维服务": 0.06,
        "技术转让收入": 0.06,
        "文案策划服务": 0.06,
        "法律咨询服务": 0.06,
        "审计服务费": 0.06,
        "市场推广费": 0.06,
        "软件销售": 0.13,
        "硬件销售": 0.13,
        "设备销售": 0.13,
        "服务器租赁收入": 0.13,
        "会议室租赁": 0.09,
        "办公用品采购": 0.13,
        "培训费支出": 0.06,
        "差旅费报销": 0.06,
        "知识产权申请": 0.06,
        "物流运输费": 0.09,
        "云服务费": 0.06,
        "网站建设支出": 0.06,
        "员工福利采购": 0.13,
    }

    # 不合规发票的特征检查清单 （定义了4项合规检查的说明书）
    COMPLIANCE_CHECKLIST = [
        {
            "id": "C001",
            "name": "备注栏是否为空",
            "description": "不动产租赁/建筑服务等特定业务需要填写备注栏",
            "check_column": "备注栏",
            "check_logic": "is_empty",
            "risk_level": "高",
            "law_reference": "国家税务总局公告2018年第28号第九条"
        },
        {
            "id": "C002",
            "name": "税率与业务类型是否匹配",
            "description": "发票税率应与业务类型对应的法定税率一致",
            "check_column": "适用税率",
            "check_logic": "rate_match",
            "risk_level": "高",
            "law_reference": "财税〔2016〕36号第十五条"
        },
        {
            "id": "C003",
            "name": "申报是否逾期",
            "description": "增值税申报应在每月15日前完成",
            "check_column": "申报日期",
            "check_logic": "is_overdue",
            "risk_level": "中",
            "law_reference": "财税〔2023〕第12号第一条"
        },
        {
            "id": "C004",
            "name": "税额计算是否准确",
            "description": "销项税额应对应收入金额×税率，进项税额应对应成本金额×税率",
            "check_column": "税额",
            "check_logic": "amount_check",
            "risk_level": "高",
            "law_reference": "财税〔2016〕36号第二十五条"
        }
    ]

    def __init__(self, file_path: str):  # 创建实例时将实例属性   加载到内存  初始化函数中的self.属性 每个实例独自的属性，相互独立，互不影响  self = "我这个对象自己的"+
        """
        初始化分析器，加载财务数据。
        
        参数：
        - file_path: Excel财务报表的路径
        """
        self.file_path = file_path   # 创建实例时，实例属性才会被赋值
        # 读取Excel文件
        self.df = pd.read_excel(file_path, engine="openpyxl")   # 将Excel表格变成 DataFrame对象，之后的操作都是对DataFrame对象操作  DataFrame对象类似表格，包含很多方法
        # 存储分析过程中发现的所有风险
        self.risks: List[Dict[str, Any]] = []
        print(f"📊 已加载财务报表：{file_path}")
        print(f"   共 {len(self.df)} 条财务记录")

    # ================================================================
    # 核心方法：执行全量合规检查 （逐行检查 + 生成报告） 这是外部调用者唯一需要调用的函数
    # ================================================================
    def run_full_analysis(self) -> Dict[str, Any]:
        """
        执行全部合规检查，返回完整分析报告。
        
        返回值：
        {
            "summary": {...},      # 汇总统计
            "risks": [...],        # 风险详情列表
            "details": [...]       # 每条记录的检查结果
        }
        """
        print("🔍 正在执行全量合规检查...")
        self.risks = []  # 清空旧结果  # 风险列表是实例属性，实例在，该实例的风险列表就一直存在，每次调用该方法时，最好清除一次风险列表

        # 逐行检查  元组拆包   iterrows()返回的是生成器，每次迭代产出一个元组  (行号,行数据) 其中行数据是pd.Series对象，可以拿来当字典用
        for index, row in self.df.iterrows():  # self.df.iterrows() 是 pandas提供的逐行遍历方法 每次循环返回两个值：行号+该行的全部数据
            self._check_row(index, row)        # 每行是一个pd.Series对象，可以像字典一样 row["业务描述"] 来取值

        # 生成汇总报告
        summary = self._generate_summary()
        
        print(f"✅ 检查完成，发现 {summary['total_risks']} 个风险项")
        return {
            "summary": summary,
            "risks": self.risks,
            "details": self.df.to_dict(orient="records")
        }

    # ================================================================
    # 单行检查逻辑 （对单行数据执行全部4项检查） 检查过程中发现的风险会被追加到self.risks列表中
    # ================================================================
    def _check_row(self, index: int, row: pd.Series):  # 本身不做任何逻检查的逻辑，只是依次调用4个检查方法
        """对单条财务记录执行所有合规检查"""

        # C001：备注栏是否为空
        self._check_remark_column(index, row)

        # C002：税率是否匹配
        self._check_rate_match(index, row)

        # C003：申报是否逾期
        self._check_overdue(index, row)

        # C004：税额计算是否准确
        self._check_amount(index, row)

    def _check_remark_column(self, index: int, row: pd.Series): # 检查逻辑：如果业务描述里包含“租赁”“建筑”“运输”等关键词，但备注栏为空，就报告风险
        """C001：检查备注栏"""
        business = str(row.get("业务描述", ""))  # 函数内部的变量只在函数执行时创建，函数结束，变量的生命周期便结束
        remark = str(row.get("备注栏", ""))

        if remark.lower() == "nan" or remark.strip() == "": # Pandas将Excel转成DF对象时，会将空单元格转成nan，而不是空字符串""
            remark = ""

        # 不动产租赁、建筑服务等特定业务必须填写备注栏
        keywords = ["租赁", "建筑", "运输"]
        if any(kw in business for kw in keywords) and remark == "":  # 同时满足业务以及空备注栏的情况下，将风险追加进风险列表  any() 里面有一个True就立即返回True
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "C001",
                "check_name": "备注栏为空",
                "risk_level": "高",
                "detail": f"业务'{business}'的发票备注栏为空，不合规",
                "suggestion": "请在备注栏填写不动产详细地址等相关信息",
                "law_reference": "国家税务总局公告2018年第28号第九条"
            })

    def _check_rate_match(self, index: int, row: pd.Series):  # 检查逻辑：将表格里的税率与法定税率作对比，差距大于0.001，就报告风险
        """C002：检查税率匹配"""
        business = str(row.get("业务描述", ""))
        rate_str = str(row.get("适用税率", ""))

        # 从税率字符串提取数字（如"6%" → 0.06）
        try:
            actual_rate = float(rate_str.replace("%", "")) / 100
        except ValueError:
            return

        # 查找该业务类型的法定税率
        expected_rate = None
        for biz_key, rate in self.TAX_RATE_MAP.items():  # 字典.items() 返回元组
            if biz_key in business:
                expected_rate = rate
                break

        # 如果找到法定税率且不匹配，记录风险
        if expected_rate is not None and abs(actual_rate - expected_rate) > 0.001:
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "C002",
                "check_name": "税率不匹配",
                "risk_level": "高",
                "detail": f"业务'{business}'适用税率{rate_str}，法定应为{expected_rate*100:.0f}%",
                "suggestion": f"请更正为{expected_rate*100:.0f}%税率",
                "law_reference": "财税〔2016〕36号第十五条"
            })

    def _check_overdue(self, index: int, row: pd.Series):
        """C003：检查申报逾期"""
        declare_date = str(row.get("申报日期", ""))  # row.get() 像字典一样取值
        business = str(row.get("业务描述", ""))

        # 检查申报日期是否晚于当月15号
        if declare_date:
            try:
                day = int(declare_date.split("-")[-1])
                if day > 15:
                    self.risks.append({
                        "row_index": int(index),
                        "business": business,
                        "check_id": "C003",
                        "check_name": "申报逾期",
                        "risk_level": "中",
                        "detail": f"业务'{business}'申报日期{declare_date}，超过当月15日",
                        "suggestion": "逾期申报将按日加收滞纳税款万分之五的滞纳金，请尽快补报",
                        "law_reference": "财税〔2023〕第12号第一条"
                    })
            except (ValueError, IndexError):
                pass

    def _check_amount(self, index: int, row: pd.Series):
        """C004：检查税额计算"""
        business = str(row.get("业务描述", ""))
        income = row.get("收入金额", 0) or 0
        cost = row.get("成本金额", 0) or 0
        output_tax = row.get("销项税额", 0) or 0
        input_tax = row.get("进项税额", 0) or 0
        rate_str = str(row.get("适用税率", ""))

        try:
            rate = float(rate_str.replace("%", "")) / 100
        except ValueError:
            return

        # 验算销项税额：收入 × 税率
        if income > 0 and abs(output_tax - income * rate) > 0.01:
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "C004",
                "check_name": "销项税额计算错误",
                "risk_level": "高",
                "detail": f"收入{income}×税率{rate_str}，应缴销项{income*rate:.2f}，实际{output_tax}",
                "suggestion": "请核实销项税额计算",
                "law_reference": "财税〔2016〕36号第二十五条"
            })

        # 验算进项税额：成本 × 税率
        if cost > 0 and abs(input_tax - cost * rate) > 0.01:
            self.risks.append({
                "row_index": int(index),
                "business": business,
                "check_id": "C004",
                "check_name": "进项税额计算错误",
                "risk_level": "高",
                "detail": f"成本{cost}×税率{rate_str}，应抵进项{cost*rate:.2f}，实际{input_tax}",
                "suggestion": "请核实进项税额计算",
                "law_reference": "财税〔2016〕36号第二十五条"
            })

    # ================================================================
    # 汇总报告生成
    # ================================================================
    def _generate_summary(self) -> Dict[str, Any]:
        """根据风险列表生成汇总统计"""
        high_risks = [r for r in self.risks if r["risk_level"] == "高"]
        mid_risks = [r for r in self.risks if r["risk_level"] == "中"]

        return {
            "total_records": len(self.df),
            "total_risks": len(self.risks),
            "high_risk_count": len(high_risks),
            "mid_risk_count": len(mid_risks),
            "risk_categories": {
                "税率问题": len([r for r in self.risks if "税率" in r["check_name"]]),
                "计算错误": len([r for r in self.risks if "计算" in r["check_name"]]),
                "发票合规": len([r for r in self.risks if "备注栏" in r["check_name"]]),
                "申报逾期": len([r for r in self.risks if "逾期" in r["check_name"]]),
            }
        }


# ================================================================
# 快速测试：直接运行此文件验证工具是否正常
# ================================================================
if __name__ == "__main__":
    import os

    # 测试数据路径（step 1生成的那份模拟数据）
    test_file = "data/sample/未来科技_2024Q3_财务数据.xlsx"

    if not os.path.exists(test_file):
        print(f"❌ 测试文件不存在：{test_file}")
        print("   请先运行 scripts/generate_sample_data.py 生成数据")
    else:
        analyzer = FinanceAnalyzer(test_file)
        report = analyzer.run_full_analysis()

        print("\n" + "=" * 50)
        print("📋 分析报告摘要")
        print("=" * 50) 
        print(f"总记录数：{report['summary']['total_records']}")
        print(f"风险总数：{report['summary']['total_risks']}")
        print(f"  · 高风险：{report['summary']['high_risk_count']}")
        print(f"  · 中风险：{report['summary']['mid_risk_count']}")

        print("\n🔴 风险详情（前13条）：")
        for risk in report["risks"][:13]:
            print(f"[第{risk['row_index'] + 1}行]  [{risk['risk_level']}风险] {risk['business']}")
            print(f"    问题：{risk['detail']}")
            print(f"    建议：{risk['suggestion']}")
            print(f"    依据：{risk['law_reference']}")
            print()