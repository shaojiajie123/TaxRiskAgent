"""
财税风险智能巡检系统 - Web 前端界面
基于 Streamlit 构建，提供文件上传、任务输入、报告展示功能
"""
import os
import sys
import streamlit as st

# 将项目根目录加入系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agents.orchestrator import TaxRiskOrchestrator

# ================================================================
# 页面配置
# ================================================================
st.set_page_config(
    page_title="财税风险智能巡检系统",
    page_icon="⚖️",
    layout="wide"
)

# ================================================================
# 标题区域
# ================================================================
st.title("⚖️ 财税风险智能巡检系统")
st.markdown("基于 RAG + AI Agent 的财税合规自动检查与智能问答平台")
st.divider()

# ================================================================
# 侧边栏：功能选择
# ================================================================
with st.sidebar:
    st.header("📋 功能选择")
    mode = st.radio(
        "请选择工作模式：",
        ["📊 财务合规检查", "💬 智能问答"],
        help="合规检查：上传Excel报表，自动分析风险\n智能问答：直接提问财税法规问题"
    )

# ================================================================
# 初始化 Agent（用缓存避免每次交互都重新初始化）
# ================================================================
@st.cache_resource
def get_agent():
    """创建并缓存主控Agent实例"""
    return TaxRiskOrchestrator()

agent = get_agent()

# ================================================================
# 模式一：财务合规检查
# ================================================================
if mode == "📊 财务合规检查":
    st.header("📊 财务合规检查")
    st.markdown("上传一份财务报表（Excel格式），系统将自动执行合规检查并生成报告。")

    # 文件上传组件
    uploaded_file = st.file_uploader(
        "选择财务报表文件（.xlsx）",
        type=["xlsx"],
        help="请上传包含业务描述、收入金额、适用税率、备注栏等字段的Excel文件"
    )

    # 任务描述输入
    task_description = st.text_input(
        "任务描述（可选）",
        value="全面检查该公司的税务合规情况",
        help="可以自定义检查任务的描述"
    )

    # 执行按钮
    if st.button("🚀 开始检查", type="primary", disabled=not uploaded_file):
        if uploaded_file is not None:
            # 保存上传的文件到临时路径
            temp_path = f"data/sample/{uploaded_file.name}"
            os.makedirs("data/sample", exist_ok=True)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"文件已上传：{uploaded_file.name}")

            # 执行分析
            with st.spinner("正在执行全量合规检查，请稍候..."):
                result = agent.execute(
                    task=task_description,
                    file_path=temp_path
                )

            # 展示结果
            st.divider()
            st.header("📋 检查报告")

            # 摘要区域
            if "summary" in result:
                st.subheader("📝 执行摘要")
                st.info(result["summary"])

            # 风险统计卡片
            if "report" in result and "summary" in result["report"]:
                summary = result["report"]["summary"]
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("审查记录总数", summary.get("total_records", 0))
                with col2:
                    st.metric("风险总数", summary.get("total_risks", 0))
                with col3:
                    st.metric("🔴 高风险", summary.get("high_risk_count", 0))
                with col4:
                    st.metric("🟡 中风险", summary.get("mid_risk_count", 0))

            # 风险详情表格
            if "report" in result and "risks" in result["report"]:
                st.subheader("🔍 风险详情")
                risks = result["report"]["risks"]
                
                # 转换为表格数据
                table_data = []
                for risk in risks:
                    table_data.append({
                        "风险等级": f"🔴 {risk['risk_level']}" if risk['risk_level'] == "高" else f"🟡 {risk['risk_level']}",
                        "业务名称": risk.get("business", ""),
                        "问题描述": risk.get("detail", ""),
                        "法律依据": risk.get("law_reference", ""),
                        "整改建议": risk.get("suggestion", "")
                    })
                
                st.dataframe(
                    table_data,
                    use_container_width=True,
                    height=400
                )

            # 高风险项的AI建议
            high_risks = [r for r in result.get("report", {}).get("risks", []) if r.get("risk_level") == "高"]
            if high_risks:
                st.subheader("🤖 AI 专业建议")
                for i, risk in enumerate(high_risks[:5], 1):
                    with st.expander(f"{i}. {risk.get('business', '未知业务')} - {risk.get('detail', '无详情')}"):
                        st.markdown(f"**法律依据：** {risk.get('law_reference', '无')}")
                        
                        # 法规原文
                        law_text = risk.get('law_full_text', '')
                        if law_text:
                            st.markdown(f"**法规原文：**")
                            st.text(law_text[:500])
                        else:
                            st.caption("（法规原文暂未检索到）")
                        
                        # AI建议
                        ai_advice = risk.get('ai_advice', '')
                        if ai_advice:
                            st.markdown(f"**AI建议：**")
                            st.info(ai_advice)
                        else:
                            st.caption("（AI建议生成中...）")

        else:
            st.warning("请先上传一份财务报表文件")

# ================================================================
# 模式二：智能问答
# ================================================================
else:
    st.header("💬 智能问答")
    st.markdown("输入财税法规相关问题，系统将基于知识库给出专业回答。")

    # 问答输入框
    query = st.text_input(
        "请输入您的财税法规问题：",
        placeholder="例如：增值税申报期限是每月几号？"
    )

    # 查询按钮
    if st.button("🔍 查询", type="primary", disabled=not query):
        with st.spinner("正在检索法规并生成回答..."):
            result = agent.execute(task=query)

        st.divider()
        st.subheader("📝 回答")

        # 显示答案
        answer = result.get("answer", "无法生成回答")
        st.markdown(answer)

        # 显示引用的法规
        references = result.get("references", [])
        if references:
            st.subheader("📎 引用法规")
            for ref in references:
                st.caption(f"· {ref.get('title', '未知法规')}（相关度：{ref.get('score', 0):.2f}）")

# ================================================================
# 页脚
# ================================================================
st.divider()
st.caption("财税风险智能巡检系统 | 基于 RAG + AI Agent | Demo v1.0")