#!/usr/bin/env python3
"""
简单计算器程序
支持基本的数学运算：加法、减法、乘法、除法
"""

import sys


def calculate(expression):
    """计算数学表达式并返回结果"""
    try:
        # 使用eval函数计算表达式
        result = eval(expression)
        return result
    except ZeroDivisionError:
        return "错误：除以零"
    except SyntaxError:
        return "错误：语法错误，请输入有效的数学表达式"
    except Exception as e:
        return f"错误：{str(e)}"


def main():
    print("=" * 40)
    print("欢迎使用简单计算器")
    print("支持的运算：+、-、*、/、()、**（幂运算）")
    print("输入'exit'或'quit'退出程序")
    print("=" * 40)
    
    while True:
        # 获取用户输入
        user_input = input("请输入表达式：").strip()
        
        # 检查是否退出
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("感谢使用计算器，再见！")
            sys.exit(0)
        
        # 计算并显示结果
        if user_input:
            result = calculate(user_input)
            print(f"结果：{result}")
        
        print()  # 空行分隔


if __name__ == "__main__":
    main()
