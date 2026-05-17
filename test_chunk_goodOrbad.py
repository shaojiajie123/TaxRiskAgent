import sys
sys.path.append(".")

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

embeddings = HuggingFaceEmbeddings(
    model_name=r"D:\AI_models\bge-small-zh-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)

vectordb = Chroma(
    persist_directory="chroma_db",
    embedding_function=embeddings
)

# 取出所有文档块
all_docs = vectordb.get()

print(f"总共 {len(all_docs['documents'])} 个文本块：\n")
for i, doc in enumerate(all_docs['documents']):
    print(f"========== 文本块 {i+1} ==========")
    print(doc)
    print()