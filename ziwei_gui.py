#!/usr/bin/env python3
# -*- coding: utf-8 -*-"""
紫微斗数排盘程序 - Windows GUI版
实现农历公历转换、紫微斗数排盘、运势分析及MD报告生成
"""

import datetime
import json
import os
from tkinter import Tk, Label, Entry, Button, Radiobutton, StringVar, Text, Scrollbar, Frame, messagebox, ttk
from tkinter.ttk import Combobox
from zhdate import ZhDate  # 农历转换库
import markdown
from weasyprint import HTML  # 用于生成PDF（可选）

# 导入现有的紫微斗数计算逻辑
from ziwei_app import ZiWeiCalculator


class ZiWeiGUI:
    """紫微斗数GUI应用"""
    def __init__(self, root):
        self.root = root
        self.root.title("紫微斗数排盘系统")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # 设置中文字体
        self.font_config = ("SimHei", 10)
        self.title_font = ("SimHei", 12, "bold")

        # 存储用户输入数据
        self.data = {
            "name": StringVar(),
            "gender": StringVar(value="男"),
            "birth_year": StringVar(),
            "birth_month": StringVar(),
            "birth_day": StringVar(),
            "birth_hour": StringVar(),
            "birth_minute": StringVar(),
            "calendar_type": StringVar(value="gregorian")  # gregorian或lunar
        }

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        """创建GUI组件"""
        # 创建主框架
        main_frame = Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== 输入区域 =====
        input_frame = Frame(main_frame)
        input_frame.pack(fill="x", pady=(0, 15))

        # 标题
        title_label = Label(input_frame, text="个人信息输入", font=self.title_font)
        title_label.grid(row=0, column=0, columnspan=4, pady=(0, 10), sticky="w")

        # 姓名
        Label(input_frame, text="姓名:", font=self.font_config).grid(row=1, column=0, sticky="e", padx=5, pady=5)
        Entry(input_frame, textvariable=self.data["name"], font=self.font_config, width=15).grid(row=1, column=1, sticky="w", pady=5)

        # 性别
        Label(input_frame, text="性别:", font=self.font_config).grid(row=1, column=2, sticky="e", padx=5, pady=5)
        Radiobutton(input_frame, text="男", variable=self.data["gender"], value="男", font=self.font_config).grid(row=1, column=3, sticky="w")
        Radiobutton(input_frame, text="女", variable=self.data["gender"], value="女", font=self.font_config).grid(row=1, column=4, sticky="w")

        # 日历类型选择
        Label(input_frame, text="日期类型:", font=self.font_config).grid(row=2, column=0, sticky="e", padx=5, pady=5)
        Radiobutton(input_frame, text="公历", variable=self.data["calendar_type"], value="gregorian", font=self.font_config).grid(row=2, column=1, sticky="w")
        Radiobutton(input_frame, text="农历", variable=self.data["calendar_type"], value="lunar", font=self.font_config).grid(row=2, column=2, sticky="w")

        # 出生日期
        Label(input_frame, text="出生年月日:", font=self.font_config).grid(row=3, column=0, sticky="e", padx=5, pady=5)
        
        # 年份选择（1900-2023）
        year_values = [str(y) for y in range(1900, 2024)]
        Combobox(input_frame, textvariable=self.data["birth_year"], values=year_values, width=6, font=self.font_config).grid(row=3, column=1, sticky="w")
        Label(input_frame, text="年", font=self.font_config).grid(row=3, column=1, sticky="e", padx=5)

        # 月份选择
        month_values = [str(m) for m in range(1, 13)]
        Combobox(input_frame, textvariable=self.data["birth_month"], values=month_values, width=4, font=self.font_config).grid(row=3, column=2, sticky="w")
        Label(input_frame, text="月", font=self.font_config).grid(row=3, column=2, sticky="e", padx=5)

        # 日期选择
        day_values = [str(d) for d in range(1, 32)]
        Combobox(input_frame, textvariable=self.data["birth_day"], values=day_values, width=4, font=self.font_config).grid(row=3, column=3, sticky="w")
        Label(input_frame, text="日", font=self.font_config).grid(row=3, column=3, sticky="e", padx=5)

        # 出生时间
        Label(input_frame, text="出生时间:", font=self.font_config).grid(row=4, column=0, sticky="e", padx=5, pady=5)
        
        # 小时选择
        hour_values = [str(h).zfill(2) for h in range(0, 24)]
        Combobox(input_frame, textvariable=self.data["birth_hour"], values=hour_values, width=4, font=self.font_config).grid(row=4, column=1, sticky="w")
        Label(input_frame, text="时", font=self.font_config).grid(row=4, column=1, sticky="e", padx=5)

        # 分钟选择
        minute_values = [str(m).zfill(2) for m in range(0, 60, 5)]
        Combobox(input_frame, textvariable=self.data["birth_minute"], values=minute_values, width=4, font=self.font_config).grid(row=4, column=2, sticky="w")
        Label(input_frame, text="分", font=self.font_config).grid(row=4, column=2, sticky="e", padx=5)

        # 按钮区域
        button_frame = Frame(input_frame)
        button_frame.grid(row=5, column=0, columnspan=5, pady=10)

        Button(button_frame, text="转换农历/公历", command=self.convert_calendar, font=self.font_config, width=15).pack(side="left", padx=5)
        Button(button_frame, text="排盘分析", command=self.calculate_ziwei, font=self.font_config, width=15).pack(side="left", padx=5)
        Button(button_frame, text="导出MD报告", command=self.export_md_report, font=self.font_config, width=15).pack(side="left", padx=5)

        # ===== 结果显示区域 =====
        result_frame = Frame(main_frame)
        result_frame.pack(fill="both", expand=True)

        Label(result_frame, text="排盘结果与运势分析", font=self.title_font).pack(anchor="w", pady=(0, 10))

        # 创建文本框和滚动条
        self.result_text = Text(result_frame, wrap="word", font=self.font_config)
        self.result_text.pack(side="left", fill="both", expand=True)

        scrollbar = Scrollbar(result_frame, command=self.result_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.result_text.config(yscrollcommand=scrollbar.set)

        # 存储计算结果
        self.ziwei_result = None

    def convert_calendar(self):
        """转换农历和公历"""
        try:
            year = int(self.data["birth_year"].get())
            month = int(self.data["birth_month"].get())
            day = int(self.data["birth_day"].get())

            if self.data["calendar_type"].get() == "gregorian":
                # 公历转农历
                gregorian_date = datetime.date(year, month, day)
                lunar_date = ZhDate.from_datetime(gregorian_date)
                messagebox.showinfo("转换结果", f"公历 {year}-{month}-{day} 对应的农历是:\n{lunar_date.lunar_year}年{lunar_date.lunar_month}月{lunar_date.lunar_day}日")
            else:
                # 农历转公历
                lunar_date = ZhDate(year, month, day)
                gregorian_date = lunar_date.to_datetime()
                messagebox.showinfo("转换结果", f"农历 {year}年{month}月{day}日 对应的公历是:\n{gregorian_date.strftime('%Y-%m-%d')}")

        except Exception as e:
            messagebox.showerror("转换错误", f"日期转换失败: {str(e)}")

    def calculate_ziwei(self):
        """计算紫微斗数命盘并显示结果"""
        try:
            # 获取用户输入
            name = self.data["name"].get().strip()
            gender = self.data["gender"].get()
            year = int(self.data["birth_year"].get())
            month = int(self.data["birth_month"].get())
            day = int(self.data["birth_day"].get())
            hour = int(self.data["birth_hour"].get())
            minute = int(self.data["birth_minute"].get())
            calendar_type = self.data["calendar_type"].get()

            # 验证输入
            if not name:
                messagebox.showwarning("输入警告", "请输入姓名")
                return

            # 如果是农历，转换为公历
            if calendar_type == "lunar":
                lunar_date = ZhDate(year, month, day)
                gregorian_date = lunar_date.to_datetime()
                year, month, day = gregorian_date.year, gregorian_date.month, gregorian_date.day

            # 创建计算器实例
            calculator = ZiWeiCalculator()
            calculator.set_birth_info(year, month, day, hour, minute, gender)

            # 计算命盘
            self.ziwei_result = calculator.calculate()
            self.ziwei_result["name"] = name  # 添加姓名信息

            # 计算运势
            current_year = datetime.datetime.now().year
            luck_years = [current_year + i for i in range(5)]  # 未来5年运势
            self.ziwei_result["luck_analysis"] = self.analyze_luck(self.ziwei_result, luck_years)

            # 显示结果
            self.display_result()

        except ValueError as e:
            messagebox.showerror("输入错误", f"请检查输入数据: {str(e)}")
        except Exception as e:
            messagebox.showerror("计算错误", f"排盘计算失败: {str(e)}")

    def analyze_luck(self, ziwei_result, years):
        """分析指定年份的运势"""
        luck_analysis = {}

        for year in years:
            # 这里简化处理，实际应根据紫微斗数流年算法计算
            # 实际应用中需要实现更复杂的流年运势分析逻辑
            luck_level = (year % 10 + ziwei_result["ming_gong"]) % 5
            luck_types = ["大吉", "吉", "平", "凶", "大凶"]
            health_advice = [
                "身体健康，精力充沛，适合积极锻炼",
                "身体状况良好，注意劳逸结合",
                "身体状况一般，注意饮食和作息",
                "身体容易疲劳，需注意健康管理",
                "健康易出问题，建议定期体检"
            ]
            career_advice = [
                "事业运极佳，适合拓展新机会",
                "事业平稳发展，有小的提升机会",
                "事业发展稳定，宜守不宜进",
                "事业面临挑战，需谨慎行事",
                "事业压力大，建议保守经营"
            ]

            luck_analysis[year] = {
                "level": luck_types[luck_level],
                "overview": f"{year}年整体运势{luck_types[luck_level]}。",
                "health": health_advice[luck_level],
                "career": career_advice[luck_level],
                "finance": "财运平平，稳健投资为宜" if luck_level < 3 else "财运波动，需谨慎理财",
                "relationship": "感情稳定，适合维系现有关系" if luck_level < 3 else "感情易有波折，需多沟通"
            }

        return luck_analysis

    def display_result(self):
        """在文本框中显示排盘结果"""
        if not self.ziwei_result:
            return

        # 清空文本框
        self.result_text.delete(1.0, "end")

        # 添加标题
        name = self.ziwei_result.get("name", "未知")
        birth_info = self.ziwei_result["birth_info"]
        self.result_text.insert("end", f"{name} 紫微斗数命盘分析\n")
        self.result_text.insert("end", f"出生日期: {birth_info['date']} {birth_info['time']} ({self.data['calendar_type'].get()})\n")
        self.result_text.insert("end", f"性别: {birth_info['gender']}\n\n")

        # 添加命盘基本信息
        self.result_text.insert("end", "=== 命盘基本信息 ===\n")
        self.result_text.insert("end", f"命宫: 第{self.ziwei_result['ming_gong']}宫\n")
        self.result_text.insert("end", f"身宫: 第{self.ziwei_result['shen_gong']}宫\n")
        self.result_text.insert("end", f"紫微星位置: 第{self.ziwei_result['ziwei_position']}宫\n\n")

        # 添加十二宫信息
        self.result_text.insert("end", "=== 十二宫星曜分布 ===\n")
        for palace in self.ziwei_result['palaces']:
            stars_str = "、".join(palace['stars']) if palace['stars'] else "无主星"
            self.result_text.insert("end", f"{palace['position']:2d}. {palace['name']:8s} : {stars_str}\n")

        # 添加四化星信息
        self.result_text.insert("end", "\n=== 四化星 ===\n")
        four_trans = self.ziwei_result['four_transformations']
        self.result_text.insert("end", f"化禄: {four_trans.get('禄', '未知')}\n")
        self.result_text.insert("end", f"化权: {four_trans.get('权', '未知')}\n")
        self.result_text.insert("end", f"化科: {four_trans.get('科', '未知')}\n")
        self.result_text.insert("end", f"化忌: {four_trans.get('忌', '未知')}\n\n")

        # 添加运势分析
        self.result_text.insert("end", "=== 未来五年运势分析 ===\n")
        for year, luck in self.ziwei_result.get('luck_analysis', {}).items():
            self.result_text.insert("end", f"【{year}年】\n")
            self.result_text.insert("end", f"整体运势: {luck['level']} - {luck['overview']}\n")
            self.result_text.insert("end", f"健康: {luck['health']}\n")
            self.result_text.insert("end", f"事业: {luck['career']}\n")
            self.result_text.insert("end", f"财运: {luck['finance']}\n")
            self.result_text.insert("end", f"感情: {luck['relationship']}\n\n")

        # 添加计算时间
        self.result_text.insert("end", f"计算时间: {self.ziwei_result['calculated_at']}\n")

    def export_md_report(self):
        """导出结果为Markdown格式报告"""
        if not self.ziwei_result:
            messagebox.showwarning("导出警告", "请先进行排盘分析")
            return

        try:
            name = self.ziwei_result.get("name", "未知")
            birth_date = self.ziwei_result['birth_info']['date']
            filename = f"紫微斗数_{name}_{birth_date}.md"

            # 创建Markdown内容
            md_content = f"# {name} 紫微斗数命盘分析\n\n"
            md_content += f"**出生日期**: {self.ziwei_result['birth_info']['date']} {self.ziwei_result['birth_info']['time']} ({'公历' if self.data['calendar_type'].get() == 'gregorian' else '农历'})\n"
            md_content += f"**性别**: {self.ziwei_result['birth_info']['gender']}\n\n"

            # 命盘基本信息
            md_content += "## 命盘基本信息\n"
            md_content += f"- 命宫: 第{self.ziwei_result['ming_gong']}宫\n"
            md_content += f"- 身宫: 第{self.ziwei_result['shen_gong']}宫\n"
            md_content += f"- 紫微星位置: 第{self.ziwei_result['ziwei_position']}宫\n\n"

            # 十二宫星曜分布
            md_content += "## 十二宫星曜分布\n"
            md_content += "| 宫位 | 名称 | 星曜 |\n"
            md_content += "|------|------|------|\n"
            for palace in self.ziwei_result['palaces']:
                stars_str = "、".join(palace['stars']) if palace['stars'] else "无主星"
                md_content += f"| {palace['position']} | {palace['name']} | {stars_str} |\n"

            # 四化星
            md_content += "\n## 四化星\n"
            four_trans = self.ziwei_result['four_transformations']
            md_content += f"- 化禄: {four_trans.get('禄', '未知')}\n"
            md_content += f"- 化权: {four_trans.get('权', '未知')}\n"
            md_content += f"- 化科: {four_trans.get('科', '未知')}\n"
            md_content += f"- 化忌: {four_trans.get('忌', '未知')}\n\n"

            # 运势分析
            md_content += "## 未来五年运势分析\n"
            for year, luck in self.ziwei_result.get('luck_analysis', {}).items():
                md_content += f"### {year}年\n"
                md_content += f"**整体运势**: {luck['level']} - {luck['overview']}\n"
                md_content += f"- **健康**: {luck['health']}\n"
                md_content += f"- **事业**: {luck['career']}\n"
                md_content += f"- **财运**: {luck['finance']}\n"
                md_content += f"- **感情**: {luck['relationship']}\n\n"

            # 计算信息
            md_content += f"*计算时间: {self.ziwei_result['calculated_at']}*\n"

            # 保存文件
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(md_content)

            messagebox.showinfo("导出成功", f"MD报告已保存到:\n{os.path.abspath(filename)}")

        except Exception as e:
            messagebox.showerror("导出错误", f"报告导出失败: {str(e)}")


if __name__ == "__main__":
    # 确保中文显示正常
    root = Tk()
    app = ZiWeiGUI(root)
    root.mainloop()
