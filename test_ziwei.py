#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试紫微斗数程序
"""

import datetime
import json

# 导入紫微斗数计算器
from ziwei_app import ZiWeiCalculator

def test_basic_calculation():
    """测试基本计算功能"""
    print("测试紫微斗数基本计算功能")
    print("=" * 50)
    
    # 创建计算器实例
    calculator = ZiWeiCalculator()
    
    # 设置测试数据：1990年5月15日 14:30，男性
    calculator.set_birth_info(1990, 5, 15, 14, 30, "男")
    
    # 测试各个计算函数
    print("1. 计算命宫位置...")
    ming_gong = calculator.calculate_ming_gong()
    print(f"   命宫: 第{ming_gong}宫")
    
    print("2. 计算身宫位置...")
    shen_gong = calculator.calculate_shen_gong()
    print(f"   身宫: 第{shen_gong}宫")
    
    print("3. 计算紫微星位置...")
    ziwei_pos = calculator.calculate_ziwei_star()
    print(f"   紫微星: 第{ziwei_pos}宫")
    
    print("4. 排列十二宫...")
    palaces = calculator.arrange_palaces()
    print(f"   十二宫排列完成，共{len(palaces)}宫")
    
    print("5. 安星...")
    palaces_with_stars = calculator.arrange_stars(palaces)
    
    print("6. 计算四化星...")
    four_trans = calculator.calculate_four_transformations()
    print(f"   四化星: {four_trans}")
    
    print("\n测试完成！")
    return True

def test_complete_chart():
    """测试完整命盘计算"""
    print("\n测试完整紫微斗数命盘计算")
    print("=" * 50)
    
    # 创建计算器实例
    calculator = ZiWeiCalculator()
    
    # 设置测试数据
    calculator.set_birth_info(1990, 5, 15, 14, 30, "男")
    
    # 计算完整命盘
    print("计算完整命盘...")
    result = calculator.calculate()
    
    # 打印结果摘要
    print(f"出生信息: {result['birth_info']}")
    print(f"命宫: 第{result['ming_gong']}宫")
    print(f"身宫: 第{result['shen_gong']}宫")
    print(f"紫微星位置: 第{result['ziwei_position']}宫")
    
    # 统计星曜分布
    star_count = 0
    for palace in result['palaces']:
        star_count += len(palace['stars'])
    print(f"总星曜数: {star_count}")
    
    # 保存测试结果
    with open('test_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("测试结果已保存到 test_result.json")
    
    print("\n完整测试完成！")
    return True

def test_multiple_cases():
    """测试多个案例"""
    print("\n测试多个出生案例")
    print("=" * 50)
    
    test_cases = [
        (1985, 8, 20, 10, 15, "女"),
        (1995, 3, 8, 22, 45, "男"),
        (2000, 12, 25, 8, 0, "女"),
    ]
    
    for i, (year, month, day, hour, minute, gender) in enumerate(test_cases, 1):
        print(f"\n案例 {i}: {year}年{month}月{day}日 {hour:02d}:{minute:02d} {gender}")
        print("-" * 40)
        
        calculator = ZiWeiCalculator()
        calculator.set_birth_info(year, month, day, hour, minute, gender)
        
        result = calculator.calculate()
        
        print(f"命宫: 第{result['ming_gong']}宫")
        print(f"身宫: 第{result['shen_gong']}宫")
        print(f"紫微星: 第{result['ziwei_position']}宫")
        
        # 显示前三个宫的星曜
        print("前三个宫星曜:")
        for palace in result['palaces'][:3]:
            stars = "、".join(palace['stars']) if palace['stars'] else "无"
            print(f"  {palace['name']}: {stars}")
    
    print("\n多案例测试完成！")
    return True

if __name__ == "__main__":
    print("开始紫微斗数程序测试")
    print("=" * 60)
    
    try:
        # 运行各个测试
        test_basic_calculation()
        test_complete_chart()
        test_multiple_cases()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()