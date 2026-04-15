#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
紫微斗数排盘程序 - Windows GUI版（简化版）
"""

import datetime
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

# 简化版的紫微斗数计算器
class SimpleZiWeiCalculator:
    """简化版紫微斗数计算器"""
    
    def __init__(self):
        self.birth_date = None
        self.birth_time = None
        self.gender = None
        
    def set_birth_info(self, year, month, day, hour, minute, gender):
        """设置出生信息"""
        self.birth_date = datetime.datetime(year, month, day)
        self.birth_time = datetime.time(hour, minute)
        self.gender = gender
        
    def calculate(self):
        """计算命盘（简化版）"""
        return {
            'birth_info': {
                'date': self.birth_date.strftime('%Y-%m-%d'),
                'time': self.birth_time.strftime('%H:%M'),
                'gender': self.gender
            },
            'ming_gong': 3,  # 简化：固定为第3宫
            'shen_gong': 6,  # 简化：固定为第6宫
            'ziwei_position': 1,  # 简化：固定为第1宫
            'palaces': [
                {'position': 1, 'name': '命宫', 'stars': ['紫微']},
                {'position': 2, 'name': '兄弟宫', 'stars': ['天机']},
                {'position': 3, 'name': '夫妻宫', 'stars': ['太阳']},
                {'position': 4, 'name': '子女宫', 'stars': ['武曲']},
                {'position': 5, 'name': '财帛宫', 'stars': ['天同']},
                {'position': 6, 'name': '疾厄宫', 'stars': ['廉贞']},
                {'position': 7, 'name': '迁移宫', 'stars': ['天府']},
                {'position': 8, 'name': '交友宫', 'stars': ['太阴']},
                {'position': 9, 'name': '官禄宫', 'stars': ['贪狼']},
                {'position': 10, 'name': '田宅宫', 'stars': ['巨门']},
                {'position': 11, 'name': '福德宫', 'stars': ['天相']},
                {'position': 12, 'name': '父母宫', 'stars': ['天梁']}
            ],
            'four_transformations': {
                '禄': '破军',
                '权': '武曲',
                '科': '太阳',
                '忌': '巨门'
            },
            'calculated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


class ZiWeiGUI:
    """紫微斗数GUI应用（简化版）"""
    def __init__(self, root):
        self.root = root
        self.root.title("紫微斗数排盘系统（简化版）")
        self.root.geometry("800x600")
        
        # 存储用户输入数据
        self.data = {
            "name": tk.StringVar(),
            "gender": tk.StringVar(value="男"),
            "birth_year": tk.StringVar(value="1990"),
            "birth_month": tk.StringVar(value="1"),
            "birth_day": tk.StringVar(value="1"),
            "birth_hour": tk.StringVar(value="12"),
            "birth_minute": tk.StringVar(value="0")
        }
        
        # 创建界面
        self.create_widgets()
        
    def create_widgets(self):
        """创建GUI组件"""
        # 输入区域
        input_frame = tk.Frame(self.root)
        input_frame.pack(padx=10, pady=10)
        
        # 标题
        tk.Label(input_frame, text="紫微斗数排盘系统（简化版）", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=4, pady=10)
        
        # 姓名
        tk.Label(input_frame, text="姓名:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(input_frame, textvariable=self.data["name"], width=15).grid(row=1, column=1, sticky="w", pady=5)
        
        # 性别
        tk.Label(input_frame, text="性别:").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        tk.Radiobutton(input_frame, text="男", variable=self.data["gender"], value="男").grid(row=1, column=3, sticky="w")
        tk.Radiobutton(input_frame, text="女", variable=self.data["gender"], value="女").grid(row=1, column=4, sticky="w")
        
        # 出生日期
        tk.Label(input_frame, text="出生日期:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        
        # 年份
        tk.Label(input_frame, text="年:").grid(row=2, column=1, sticky="w")
        tk.Entry(input_frame, textvariable=self.data["birth_year"], width=6).grid(row=2, column=2, sticky="w")
        
        # 月份
        tk.Label(input_frame, text="月:").grid(row=2, column=3, sticky="w")
        tk.Entry(input_frame, textvariable=self.data["birth_month"], width=4).grid(row=2, column=4, sticky="w")
        
        # 日期
        tk.Label(input_frame, text="日:").grid(row=2, column=5, sticky="w")
        tk.Entry(input_frame, textvariable=self.data["birth_day"], width=4).grid(row=2, column=6, sticky="w")
        
        # 出生时间
        tk.Label(input_frame, text="出生时间:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        
        # 小时
        tk.Label(input_frame, text="时:").grid(row=3, column=1, sticky="w")
        tk.Entry(input_frame, textvariable=self.data["birth_hour"], width=4).grid(row=3, column=2, sticky="w")
        
        # 分钟
        tk.Label(input_frame, text="分:").grid(row=3, column=3, sticky="w")
        tk.Entry(input_frame, textvariable=self.data["birth_minute"], width=4).grid(row=3, column=4, sticky="w")
        
        # 按钮
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="排盘分析", command=self.calculate_ziwei, width=15).pack(side="left", padx=5)
        tk.Button(button_frame, text="清空结果", command=self.clear_results, width=15).pack(side="left", padx=5)
        
        # 结果显示区域
        result_frame = tk.Frame(self.root)
        result_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(result_frame, text="排盘结果:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))
        
        # 创建文本框和滚动条
        self.result_text = tk.Text(result_frame, wrap="word", height=20)
        self.result_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = tk.Scrollbar(result_frame, command=self.result_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.result_text.config(yscrollcommand=scrollbar.set)
        
    def calculate_ziwei(self):
        """计算紫微斗数命盘"""
        try:
            # 获取用户输入
            name = self.data["name"].get().strip()
            gender = self.data["gender"].get()
            year = int(self.data["birth_year"].get())
            month = int(self.data["birth_month"].get())
            day = int(self.data["birth_day"].get())
            hour = int(self.data["birth_hour"].get())
            minute = int(self.data["birth_minute"].get())
            
            # 验证输入
            if not name:
                messagebox.showwarning("输入警告", "请输入姓名")
                return
            
            # 创建计算器实例
            calculator = SimpleZiWeiCalculator()
            calculator.set_birth_info(year, month, day, hour, minute, gender)
            
            # 计算命盘
            result = calculator.calculate()
            result["name"] = name
            
            # 显示结果
            self.display_result(result)
            
        except ValueError as e:
            messagebox.showerror("输入错误", f"请检查输入数据: {str(e)}")
        except Exception as e:
            messagebox.showerror("计算错误", f"排盘计算失败: {str(e)}")
    
    def display_result(self, result):
        """显示排盘结果"""
        # 清空文本框
        self.result_text.delete(1.0, "end")
        
        # 添加标题
        name = result.get("name", "未知")
        birth_info = result['birth_info']
        self.result_text.insert("end", f"{name} 紫微斗数命盘分析\n")
        self.result_text.insert("end", f"出生日期: {birth_info['date']} {birth_info['time']}\n")
        self.result_text.insert("end", f"性别: {birth_info['gender']}\n\n")
        
        # 添加命盘基本信息
        self.result_text.insert("end", "=== 命盘基本信息 ===\n")
        self.result_text.insert("end", f"命宫: 第{result['ming_gong']}宫\n")
        self.result_text.insert("end", f"身宫: 第{result['shen_gong']}宫\n")
        self.result_text.insert("end", f"紫微星位置: 第{result['ziwei_position']}宫\n\n")
        
        # 添加十二宫信息
        self.result_text.insert("end", "=== 十二宫星曜分布 ===\n")
        for palace in result['palaces']:
            stars_str = "、".join(palace['stars']) if palace['stars'] else "无主星"
            self.result_text.insert("end", f"{palace['position']:2d}. {palace['name']:8s} : {stars_str}\n")
        
        # 添加四化星信息
        self.result_text.insert("end", "\n=== 四化星 ===\n")
        four_trans = result['four_transformations']
        self.result_text.insert("end", f"化禄: {four_trans.get('禄', '未知')}\n")
        self.result_text.insert("end", f"化权: {four_trans.get('权', '未知')}\n")
        self.result_text.insert("end", f"化科: {four_trans.get('科', '未知')}\n")
        self.result_text.insert("end", f"化忌: {four_trans.get('忌', '未知')}\n\n")
        
        # 添加计算时间
        self.result_text.insert("end", f"计算时间: {result['calculated_at']}\n")
    
    def clear_results(self):
        """清空结果"""
        self.result_text.delete(1.0, "end")


if __name__ == "__main__":
    root = tk.Tk()
    app = ZiWeiGUI(root)
    root.mainloop()