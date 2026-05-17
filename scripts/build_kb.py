"""
知识库构建脚本（优化分块版）
改进：先按 --- 分隔符拆开每条法规，确保独立成块
"""
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import TextLoader # 文档加载器
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma         # 向量数据库    
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

load_dotenv()

RAW_DATA_PATH = "data/raw/税法知识库.txt"
CHROMA_DB_PATH = "chroma_db"
CHUNK_SIZE = 800        # 单条法规通常不会超过800字，设为上限
CHUNK_OVERLAP = 0       # 法规之间不需要重叠，它们是独立的
LOCAL_MODEL_PATH = r"D:\AI_models\bge-small-zh-v1.5"

def main():
    print("📄 加载文档...")
    loader = TextLoader(RAW_DATA_PATH, encoding="utf-8")
    docs = loader.load()
    raw_text = docs[0].page_content
    print(f"   原始文档共 {len(raw_text)} 个字符")

    # ---- 关键优化：先按 --- 拆开每条法规 ----
    print("✂️ 按 '---' 拆分法规...")
    # 按 --- 分割，得到每条独立的法规文本
    raw_chunks = raw_text.split("\n---\n")
    # 过滤掉空白块
    raw_chunks = [chunk.strip() for chunk in raw_chunks if chunk.strip()]
    print(f"   拆分出 {len(raw_chunks)} 条独立法规")

    # 为每条法规创建一个Document对象
    documents = []
    for i, chunk in enumerate(raw_chunks):
        # 从法规文本的第一行提取标题作为元数据
        lines = chunk.split("\n")
        title = lines[1] if len(lines) > 1 else f"法规片段{i+1}"
        documents.append(Document(
            page_content=chunk,
            metadata={"source": RAW_DATA_PATH, "title": title, "chunk_index": i}
        ))

    # ---- 如果某条法规仍然太长，做二次切分 ----
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n", "。", "；", "，", " ", ""]
    )       
    
    final_chunks = []
    for doc in documents:
        if len(doc.page_content) > CHUNK_SIZE:
            # 这条法规太长，需要再切
            sub_chunks = text_splitter.split_documents([doc])
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(doc)
    
    print(f"   最终共 {len(final_chunks)} 个文本块")

    # ---- 向量化并存储 ----
    print("🧠 加载本地嵌入模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name=LOCAL_MODEL_PATH,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )
    print("   模型加载完成")

    print("🔢 向量化并存储...")
    import shutil
    if os.path.exists(CHROMA_DB_PATH):
        shutil.rmtree(CHROMA_DB_PATH)

    vectordb = Chroma.from_documents(
        documents=final_chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DB_PATH
    )

    print(f"✅ 构建成功！{len(final_chunks)} 个文本块已存入 {CHROMA_DB_PATH}")
    
    # 预览每条法规的标题
    print("\n📋 法规清单预览：")
    for doc in final_chunks:
        title = doc.metadata.get("title", "无标题")
        length = len(doc.page_content)
        print(f"   · {title} ({length}字)")

# 只有直接运行此文件时，才会执行以下代码，被其他模块导入时，不执行以下代码。这样做的好处是：这个文件技能作为独立程序运行(测试功能),又能被其他模块干净的导入(不会执行测试代码)
if __name__ == "__main__":
    main()