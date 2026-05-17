"""
混合检索引擎
结合 BM25 关键词检索 + 向量语义检索，通过加权融合排序输出最终结果
"""
import os
import sys
import jieba
import numpy as np
from typing import List, Tuple, Dict, Any

# 将项目根目录加入系统路径 因为这有这样才能在当前脚本中导入(找到)其他脚本模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi


class HybridRetriever:  # 混合检索 = 多路召回（向量检索+BM25） + 融合排序
    """
    混合检索器
    - BM25：擅长关键词精确匹配（如法条号、税率数字）
    - 向量检索：擅长语义理解（如口语化查询）
    - 融合排序：加权合并两路结果，互补优势
    """

    def __init__(
        self,
        chroma_db_path: str = "chroma_db",                # 向量数据库路径
        model_path: str = r"D:\AI_models\bge-small-zh-v1.5",  # 本地嵌入模型路径
        alpha: float = 0.5                                 # 融合权重（0=纯向量，1=纯BM25）
    ):
        """
        初始化混合检索器
        参数说明：
        - chroma_db_path: ChromaDB持久化目录
        - model_path: 本地嵌入模型的文件夹路径
        - alpha: BM25的权重。0.5表示两路各占一半
        """
        # ---- 第1步：加载向量检索引擎 ----
        # 为什么要同一个模型？因为向量空间必须一致。
        # 用模型A建库、模型B检索，就像用中文地图找英文地址，永远对不上。
        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_path,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        # 加载已持久化的ChromaDB
        self.vectordb = Chroma(
            persist_directory=chroma_db_path,    # 指定到哪个知识库进行检索，到时候就到这个知识库去将用户的query embedding 和 库里的chunk embedding进行相似度计算
            embedding_function=self.embeddings   # 指定好用什么embedding模型，到时候就用这个模型来对用户的query进行embedding and retrieve
        )

        # ---- 第2步：构建BM25关键词检索引擎 ----
        # 从ChromaDB中取出所有文档块的文本
        # vectordb.get() 返回一个字典，包含 documents、metadatas、ids 等字段
        all_data = self.vectordb.get() # 把数据库里的数据搬到内存中
        # all_data = {
        #   "ids" : ["文本块1的唯一标识","文本块2的唯一标识","文本块3的唯一标识"],
        #   "documents" : ["文本块1的全文","文本块2的全文","文本块3的全文","文本块n的全文"],
        #   "metadatas" : []
        #   }
        self.all_docs = all_data["documents"]       # 列表，每个元素是一个文档块的文本  即6条法规的文本内容 ["法规1", "法规2", "法规3"]
        self.all_metadatas = all_data["metadatas"]  # 列表，每个元素是对应的元数据      即6条法规的元数据  ["source":... , "tittle": ....]

        # BM25 需要分词后的文本（它不理解中文，必须先用jieba分词）
        # 例如："增值税税率" → ["增值税", "税率"]
        tokenized_docs = [list(jieba.cut(doc)) for doc in self.all_docs]  # 列表推导式 先执行for doc in self.all_docs  jieba.cut()会返回一个生成器，我们需要用list()将它转成Python列表
        self.bm25 = BM25Okapi(tokenized_docs)       # 创建BM25索引

        # 融合权重
        self.alpha = alpha

        print(f"✅ HybridRetriever 初始化完成")
        print(f"   文档块数量：{len(self.all_docs)}")
        print(f"   融合权重 alpha：{self.alpha}（0=纯向量，1=纯BM25）")

    # ============================================================
    # 核心方法：混合检索
    # ============================================================
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = None
    ) -> List[Tuple[str, float, Dict[str, Any]]]:   # 文档 文档得分 文档元数据(来源 标题)
        """
        执行混合检索，返回融合排序后的 top_k 个结果。
        
        参数：
        - query: 用户输入的查询文本
        - top_k: 返回的结果数量
        - alpha: 临时指定的融合权重（不指定则用初始化时的值）
        
        返回值：
        列表，每个元素是 (文档内容, 融合得分, 元数据) -> （str, float, dict[str,any]）
        """
        # 如果调用时指定了alpha，就用调用时的；否则用初始化时的
        if alpha is not None:
            self.alpha = alpha

        # ---- 第1步：并行执行两路检索 ----
        # 向量检索：用余弦相似度找语义最接近的文档块
        vec_results = self.vectordb.similarity_search_with_score(query, k=top_k * 2)    # 相似度计算仅仅只需一行代码？
        # vec_results 格式: [(Document对象, 距离得分), ...]  列表，每个元素是元组
        # 注意：Chroma返回的是“距离”，越小越相似。我们需要转成“相似度”，越大越相似。
        vec_dict = {}  # {文档内容: 相似度得分}  vec_dict是字典，键是文本内容，值是该文本内容的相似度得分 {str:float}
        for doc, distance in vec_results:    # 元组拆包 ： 每次循环从vec_results这个列表容器中拿出一个元组，将元组的Document对象赋值给doc，将元组的距离赋值给distance，然后开始循环体
            # 距离 → 相似度：距离越小，相似度越高
            similarity = 1.0 / (1.0 + distance) # 分母为什么要+1？因为distance可能为0 
            vec_dict[doc.page_content] = similarity # doc是Document对象(LangChain的对象),doc.page_content表示这个对象里面包含的文本。以doc里面的文本为键，以相似度得分为值，存入字典
    
        # BM25检索：分词后计算关键词匹配得分
        tokenized_query = list(jieba.cut(query))    # tokenized_query = ["申报", "期限", "是", "几", "号", "？"]
        bm25_scores = self.bm25.get_scores(tokenized_query)    # bm25_scores 是一个长度为6的数组（对应6个文档块），每个元素是该文档的BM25得分
        # bm25_scores 是一个数组，长度等于文档总数，每个元素是对应文档的得分
        # bm25_scores = [0.0, 0.0, 1.2, 8.5, 0.0, 0.0]
        #                 ↑    ↑    ↑    ↑    ↑    ↑
        #                块0   块1  块2  块3  块4  块5
#                     (块3是"财税〔2023〕第12号"，得分最高，因为它包含"申报""期限")

        # 取BM25得分最高的 top_k*2 个文档    # bm25_top_indices = [3, 2, ...]  → 得分从高到低的文档索引，注意是索引！
        bm25_top_indices = np.argsort(bm25_scores)[::-1][:top_k * 2]    # argsort()返回从小到大的索引 [::-1]代表反转 即把列表倒序 [:top_k * 2]代表返回前tok_k * 2个元素，其他的忽略掉
        # bm25_top_indices = [3, 2, 0, 1, 4, 5]
        bm25_dict = {}  # {文档内容: BM25得分}
        for idx in bm25_top_indices:  # 循环的是索引列表而不是普通列表 idx并不是从0开始的索引 而是被容器赋值的变量（即得分从高到低的文档的索引）！
            if bm25_scores[idx] > 0:  # 只保留得分大于0的（至少命中了一个词）等于0的不要
                bm25_dict[self.all_docs[idx]] = float(bm25_scores[idx])
        # bm25_dict = {
        #     "文号：财税〔2023〕第12号...": 8.5,   
        #     "文号：公告2019年第39号...": 1.2,
        # }

        # ---- 第2步：归一化 ----
        # 为什么要归一化？
        # BM25的得分可能是 0~50，向量相似度是 0~1，量纲不同，无法直接相加。
        # 归一化后两路分数都在 0~1 之间，公平比较。  归一化后仍是 {文档，文档得分} 的数据结构
        vec_scores_norm = self._normalize(vec_dict)   # vec_scores_norm = {"财税〔2023〕第12号...": 1.0, "...":0.....,.....}
        bm25_scores_norm = self._normalize(bm25_dict)   

        # ---- 第3步：融合排序（融合得分计算） ----
        # 收集两路返回的所有文档（去重）
        all_doc_keys = set(vec_dict.keys()) | set(bm25_dict.keys())  # 利用集合可以取交集这个特性，实现文档的去重
        
        fused = {}  # {文档内容: 融合得分}
        for doc in all_doc_keys:
            score_vec = vec_scores_norm.get(doc, 0.0)  # get()是字典的方法，get(doc,0.0)中doc是键，如果doc存在，那么就返回doc这个键的值，没有就返回默认值0.0
            score_bm25 = bm25_scores_norm.get(doc, 0.0)
            # 加权融合公式：alpha × BM25得分 + (1-alpha) × 向量得分
            fused[doc] = self.alpha * score_bm25 + (1 - self.alpha) * score_vec

        # 按融合得分降序排列，取 top_k
        sorted_docs = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]   # fused.items() -> 把字典变成键值对元组的列表  key=lambda x: x[1] -> 按得分来排序
        #   fused.items() = [
        #   ("财税〔2023〕第12号...", 1.0),
        #   ("公告2019年第39号...", 0.212),
        #   ("公告2018年第28号...", 0.102),
        #   ("国税发〔2009〕2号...", 0.0),
        # ] 

        #   sorted_docs = [   取前top_k个结果 
        #   ("财税〔2023〕第12号...", 1.0),
        #   ("公告2019年第39号...", 0.212),
        #   ("公告2018年第28号...", 0.102),
        # ]

        # ---- 第4步：整理返回结果 ----
        results = []  # [(文档内容, 融合得分, 元数据),(str,float,dict),(str,float,dict),...,(str,float,dict)]  即把sorted_docs这个二元组列表变成results这个三元组列表 也就是多了个metadata字段  
        for doc_content, score in sorted_docs:
            # 找到这个文档对应的元数据
            try:
                idx = self.all_docs.index(doc_content)  # 列表.index(元素) -> 返回这个元素的索引值
                metadata = self.all_metadatas[idx]
            except ValueError:
                metadata = {}
            results.append((doc_content, score, metadata))

        return results

    # ============================================================
    # 辅助方法：Min-Max 归一化
    # ============================================================
    def _normalize(self, score_dict: Dict[str, float]) -> Dict[str, float]:  # 输出一个得分字典 输出一个得分字典
        """
        将得分归一化到 [0, 1] 区间。
        公式：(x - min) / (max - min)
        如果所有得分相同，统一返回 0.5。
        """
        if not score_dict:
            return {}
        
        scores = list(score_dict.values())  # 获取字典中的所有得分，并存入列表中
        min_s, max_s = min(scores), max(scores)    # 获取得分列表中的最大值和最小值 保存到变量min_s 和 max_s中
        
        if max_s == min_s:
            # 所有得分一样，返回中间值
            return {k: 0.5 for k in score_dict} # 字典推导式 先执行 for k in socre_dict 然后再执行 k:0.5,这里我们只用到键，所以不需要把字典给itmes()
        
        return {k: (v - min_s) / (max_s - min_s) for k, v in score_dict.items()}  # 字典推导式 如果需要把容器里面的键和值都拿出来用的话，需要先 字典.items()

    # ============================================================
    # 辅助方法：动态调整融合权重
    # ============================================================
    def set_alpha(self, alpha: float):
        """动态调整融合权重。0=纯向量，1=纯BM25"""
        self.alpha = alpha
        print(f"   🔧 alpha 已调整为 {self.alpha}")


# ============================================================
# 测试代码：运行此文件可直接验证混合检索效果  本模块被其他模块导入时，以下代码不会执行，所以天然适合作为本模块的测试代码
# ============================================================
if __name__ == "__main__":
    # 初始化检索器
    retriever = HybridRetriever(alpha=0.5)  # 手动设置参数alpha为0.5 否则默认用初始化函数设置的值

    # 测试查询
    test_queries = [
        "不动产租赁的增值税税率是多少？",     # 偏向语义理解
        "财税〔2016〕36号",                  # 偏向关键词精确匹配
        "发票备注栏没填写有什么后果？",
        "申报期限是几号？",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f"❓ 查询：{q}")
        print(f"{'='*60}")
        
        results = retriever.retrieve(q, top_k=3)
        
        for i, (content, score, meta) in enumerate(results, 1):  # 1 代表 i从1开始自增 
            title = meta.get("title", "无标题")
            print(f"\n  结果 {i}（得分: {score:.4f} | {title}）")
            print(f"  {content[:150]}...")