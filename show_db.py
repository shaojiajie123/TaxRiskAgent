import sqlite3
# 连接到那个文件
conn = sqlite3.connect('chroma_db/chroma.sqlite3')
cursor = conn.cursor()
# 看看里面有哪些表格
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("数据库里的表格:", cursor.fetchall())
conn.close()