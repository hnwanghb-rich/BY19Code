import os

# 获取当前目录
current_dir = os.getcwd()
print(f"当前目录: {current_dir}")
print("=" * 50)

# 列出所有文件和目录
items = os.listdir('.')
items.sort()  # 按名称排序

print("文件和目录列表:")
for item in items:
    # 检查是否是目录
    if os.path.isdir(item):
        print(f"  [目录] {item}/")
    else:
        print(f"  [文件] {item}")

print(f"\n总计: {len(items)} 个项目")