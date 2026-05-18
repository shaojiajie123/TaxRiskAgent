# TaxRiskAgent - 财税法律 AI Agent 系统

## 项目简介
基于 RAG（检索增强生成）技术的财税法律智能助手，支持：
- 财税法规的混合检索（BM25 + 向量语义）
- 用户意图自动分类（筹划型 / 争议型 / 合规型 / 知识型）
- 财务数据合规自动检查与风险报告生成

## 功能演示
### 智能问答
> 用户：增值税申报期限是每月几号？
> 系统：根据《关于进一步明确增值税申报期限的通知》（财税〔2023〕第12号）第一条，增值税一般纳税人的纳税申报期限为每月15日前。遇法定节假日，申报期限顺延。逾期申报的，按日加收滞纳税款万分之五的滞纳金。

### 财务合规分析
> 加载财务报表后，系统自动识别出：
> - 高风险：服务器租赁收入税率应为13%而非6%
> - 高风险：服务器租赁、会议室租赁等备注栏为空
> - 中风险：多条记录申报日期逾期

## 技术栈
- 语言：Python 3.11+
- 向量数据库：ChromaDB
- 嵌入模型：BAAI/bge-small-zh-v1.5（本地部署）
- 大模型：DeepSeek API
- 前端：Streamlit（规划中）

## 快速开始
### 1. 环境准备
# 创建虚拟环境
python -m venv venv
# 激活虚拟环境（Windows）
venv\Scripts\activate
# 安装依赖
pip install -r requirements.txt

### 2. 配置 API 密钥
在项目根目录创建 `.env` 文件，填入：
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com

### 3. 构建知识库
python scripts/build_kb.py

### 4. 运行测试
测试混合检索
python src/rag/hybrid_retriever.py
测试意图分类
python src/rag/intent_classifier.py
测试完整问答
python src/rag/answer_generator.py
测试财务合规分析
python src/tools/finance_analyzer.py

## 项目结构
TaxRiskAgent/
├── data/ # 数据目录
│ ├── raw/ # 原始法规文档
│ └── sample/ # 模拟财务数据
├── scripts/ # 构建与生成脚本
│ ├── build_kb.py # 知识库构建
│ └── generate_sample_data.py # 模拟数据生成
├── src/ # 核心代码
│ ├── rag/ # RAG 检索模块
│ │ ├── hybrid_retriever.py # 混合检索引擎
│ │ ├── intent_classifier.py # 意图分类器
│ │ └── answer_generator.py # 答案生成器
│ └── tools/ # 工具模块
│ ├── finance_analyzer.py # 财务合规分析
│ └── enhanced_analyzer.py # 增强版分析（分析+法规检索）
├── requirements.txt # 项目依赖
├── .gitignore # Git 忽略配置
└── README.md # 项目说明

## 架构说明
用户输入 → 意图分类器 → 混合检索器(BM25+向量) → 答案生成器 → 输出
                          ↑
                      知识库(ChromaDB)