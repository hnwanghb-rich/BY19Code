import os
print("当前目录:", os.getcwd())
print("文件列表:")
for item in os.listdir('.'):
    print(f"  {item}")