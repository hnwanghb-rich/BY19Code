#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试紫微斗数程序
直接运行，不依赖外部命令
"""

print("简单测试紫微斗数程序")
print("=" * 50)

# 模拟紫微斗数计算器的基本功能
class SimpleZiWei:
    def __init__(self):
        self.palaces = ["命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
                       "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫"]
        
    def calculate(self, year, month, day, hour):
        """简化计算"""
        # 命宫位置简化计算
        ming_gong = (month + hour) % 12
        if ming_gong == 0:
            ming_gong = 12
            
        # 紫微星位置简化计算
        ziwei_pos = (day + 5) % 12
        if ziwei_pos == 0:
            ziwei_pos = 12
            
        return {
            'ming_gong': ming_gong,
            'ziwei_pos': ziwei_pos,
            'ming_gong_name': self.palaces[ming_gong-1],
            'ziwei_pos_name': self.palaces[ziwei_pos-1]
        }

# 测试
calculator = SimpleZiWei()

# 测试案例
test_cases = [
    (1990, 5, 15, 14),
    (1985, 8, 20, 10),
    (1995, 3, 8, 22),
]

print("测试案例结果：")
print("-" * 50)

for i, (year, month, day, hour) in enumerate(test_cases, 1):
    result = calculator.calculate(year, month, day, hour)
    print(f"案例 {i}: {year}年{month}月{day}日 {hour}时")
    print(f"  命宫: 第{result['ming_gong']}宫 ({result['ming_gong_name']})")
    print(f"  紫微星: 第{result['ziwei_pos']}宫 ({result['ziwei_pos_name']})")
    print()

print("=" * 50)
print("测试完成！")
print()
print("要运行完整的紫微斗数程序，请执行：")
print("  python ziwei_app.py")
print()
print("文件已创建：")
print("  1. ziwei_app.py - 完整的紫微斗数排盘程序")
print("  2. test_ziwei.py - 测试脚本")
print("  3. simple_test.py - 这个简单测试脚本")
print("  4. run_test.bat - Windows批处理测试文件")