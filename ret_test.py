import sys
sys.path.append(".")

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

embeddings = HuggingFaceEmbeddings(
    model_name=r"D:\AI_models\bge-small-zh-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)

vectordb = Chroma(persist_directory="chroma_db", embedding_function=embeddings)

queries = [
    "发票备注栏没填有什么后果？",
    "增值税什么时候申报？",
    "关联交易怎么定价才不会被查？",
    "增值税税率是多少？"
]

for q in queries:
    print(f"❓ {q}")
    results = vectordb.similarity_search(q, k=2)
    for j, doc in enumerate(results):
        title = doc.metadata.get("title", "无标题")
        print(f"  结果{j+1}: {title}")
    print()