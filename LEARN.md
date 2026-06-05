项目架构：
=====================================================================
TaxRiskAgent/                  # 项目根目录
├── .env                       # 存放API密钥等敏感配置（不上传Git）
├── .gitignore                 # Git忽略文件配置
├── requirements.txt           # 项目依赖清单
├── README.md                  # 项目说明
│
├── data/                      # 数据目录
│   ├── raw/                   # 原始文档（PDF、网页爬虫结果）
│   ├── processed/             # 处理后的数据（切分好的文本块）
│   ├── sample/                # 模拟客户数据（带风险的财务报表）
│   └── external/              # 外部数据（裁判文书、法规）
│
├── src/                       # 核心源代码
│   ├── __init__.py
│   ├── agents/                # Agent定义与编排
│   │   ├── __init__.py
│   │   ├── orchestrator.py   # 主控Agent，负责任务分解与调度
│   │   ├── data_agent.py     # 数据获取子Agent
│   │   ├── policy_agent.py   # 政策检索子Agent
│   │   ├── risk_agent.py     # 风险计算子Agent
│   │   └── report_agent.py   # 报告生成子Agent
│   │
│   ├── rag/                   # RAG检索模块
│   │   ├── __init__.py
│   │   ├── retriever.py      # 混合检索引擎
│   │   ├── knowledge_base.py # 知识库构建与更新
│   │   └── embeddings.py     # 向量化相关
│   │
│   ├── tools/                 # 工具集（Agent的手和脚）
│   │   ├── __init__.py
│   │   ├── file_parser.py    # 文件解析（Excel/PDF/发票）
│   │   ├── calculator.py     # 税额验算
│   │   ├── web_search.py     # 网页搜索与爬虫
│   │   └── rule_engine.py    # 硬编码业务规则（如税率对照）
│   │
│   ├── memory/                # 记忆管理
│   │   ├── __init__.py
│   │   └── check_history.py  # 检查记录存储与对比
│   │
│   └── ui/                    # 前端交互界面
│       ├── __init__.py
│       └── app.py            # Streamlit应用入口
│
├── tests/                     # 测试用例
│   ├── test_retriever.py
│   └── test_agents.py
│
└── scripts/                   # 辅助脚本
    ├── build_kb.py            # 知识库初始化构建
    └── generate_sample_data.py # 模拟数据生成脚本
====================================================================

# 项目第一天
    --进度
    创建项目TaxRiskAgent
    创建项目的子目录 data模块 scripts模块 scr模块 tests模块
    创建项目的子文件 .gitignore文件 .venv文件 requirements.txt文件 README.md文件
    创建项目的虚拟环境 venv,用于安装本项目的依赖，防止全局python污染本项目
    pip install -r requirements.txt 安装本项目的依赖到 venv中
    scripts文件底下创建generate_sample_data.py文件，用于生成模拟数据
    新建文件data/raw/税法知识库.txt ，模拟法规文档，作为本项目的知识库。真实的法规文档来自国家税务总局等官方渠道
    编写知识库构建脚本scripts/build_kb.py，负责把原始法规文档 加载 切片 向量化 存入向量数据库
    --问题
    依旧GBK编码问题，txt中不要出现中文字符
    安装chromadb相关库出现报错，原因是版本不对，安装最新版本的即可
    嵌入依赖冲突迟迟解决不了，直接重新创建虚拟环境，且requirements.txt中不写依赖的版本号
    嵌入模型不再选择deepseek-embedding(究竟有没有这个模型？)，直接选择本地的bge模型，对中文的嵌入效果非常好，然后就是
    卸载掉lanchain-openai的包，因为会污染全局环境，我们安装sentence-transformers这个库来加载我们的本地嵌入模型
    我注意到每次加载模型都得花上好几秒钟
    

    知识点：
    先准备模拟数据(6条法律条文)
    然后建立知识库(导入条文、导入切分器、切分条文为chunk、加载embedding模型然后将chunk向量化、存入向量数据库)
    然后测试结果，模拟用户输入，用embedding模型将用户输入向量化、然后去向量数据库检索语义最相关的top-n个结果，返回给用户

# 项目第二天
    --进度
    1-新增混合检索脚本hybird_retriever.py，用于rag多路召回。该脚本需要用到已经创建好的向量数据库，因为执行检索时需要指定检索哪一个数据库，
    所以该脚本一定得是build_kb.py脚本执行后，创建了向量数据库以后，才能运行。向量数据库都没创建好，检索也就无从谈起了！
    2-学习了for循环，明白了元组拆包，for aa, bb in cc 代表着：每次循环时，从cc这个容器里取出本轮的元素(在这里这个元素是元组),将元组中的第一个元素赋值给aa，第二个元素赋值给bb，
    然后开始执行循环体，直到循环结束。这个for循环经常出现在需要对一个列表进行循环，而这个列表的元素是多个二元组。用两个变量(aa,bb)才能够将元组进行拆包，若是一个变量的话，直接返回
    该元组本身，而不进行拆包！

# 项目第三天
    --进度
    1-新增intent_classifier.py 用户意图分类器，用LLM将用户查询进行意图分类，方便后续调整不同的检索权重，以及走不同的agent流程(知识型的意图就走知识agent，合规型的意图就走合规agent等等)
    2-新增answer_generator.py 用于让LLM根据检索到的文档生成回答。 意图识别 + 混合检索 + 答案生成。构成了RAG的完整流程

# 项目第四天
    --进度
    1.新增finance_analyzer.py，财务风险分析器，作用：扫描财务Excel，检查其存在的风险，追进进风险列表，并生成初步的风险报告

# 项目第五天
    --进度
    1.新增enhanced_analyzer.py,增强分析器，继承自风险分析器，在风险分析器的基础之上，增加了检索功能，相比父类，它实现了将风险进行检索，然后返回该风险对应的法规全文(最相关的TOP_1)
    ，因为父类中的风险列表中，只有依据来源只有法律文号，我们需要给我们的客户(律师)，提供更多的有效信息，就比如刚刚提到的法规全文，若是只提供法律文号，律师就得按照这个法律文号自己去
    搜索相关法规全文，若我们在代码中实现根据风险返回对应的法规文号以及法规全文的话，就大大的减少律师的工作时间，方便了律师查看该风险对应的法规全文。