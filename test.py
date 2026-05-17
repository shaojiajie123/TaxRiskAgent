fruits = ["水果","西瓜","橘子","香蕉"]

for fruit in fruits:
    print(fruit)

print("=====================")

persons = [("张三", 20),("李四", 21),("王五", 22),("赵六", 23)]

for name, age in persons:
    print(f"{name} 今年 {age} 岁了")

print("================================")

for name in persons:
    print(name)

print("===================================")

persons = [("张三", 20, "成都"),("李四", 21, "重庆"),("王五", 22, "上海"),("赵六", 23, "武汉")]

for name, age, adress in persons:
    print(f"{name}今年 {age} 岁了，老家在 {adress}")

print("=========================================")

for name in persons:
    print(f"{name}")

# enumerate  = "编号机" 同时返还给你元素以及元素的索引
print("=======================================")
fruits = ["西瓜", "香蕉", "橘子"]

for idx, fruit in enumerate(fruits):
    print(idx, fruit)

# ============ 元组拆包 ==============================
score_tuple_dict = [("math",99), ("chinese",95), ("english",94)]
score_dict = {}

for subject, score in score_tuple_dict:  # 元组拆包  每次循环，会把当前元组的第一个元素赋值给subject , 第二个元素赋值给score，然后我们在循环体中去使用这两个变量
    score_dict[subject] = score

print(score_dict)