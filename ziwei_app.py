#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
紫微斗数排盘程序
基于出生年月日时计算紫微斗数命盘
"""

import datetime
import json
from typing import Dict, List, Tuple, Optional


class ZiWeiCalculator:
    """紫微斗数计算器"""
    
    # 十二宫名称
    PALACES = [
        "命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
        "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫"
    ]
    
    # 十四主星
    MAIN_STARS = [
        "紫微", "天机", "太阳", "武曲", "天同", "廉贞",
        "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军"
    ]
    
    # 辅星
    MINOR_STARS = [
        "左辅", "右弼", "文昌", "文曲", "天魁", "天钺",
        "禄存", "擎羊", "陀罗", "火星", "铃星", "地空", "地劫"
    ]
    
    # 四化星
    TRANSFORM_STARS = ["化禄", "化权", "化科", "化忌"]
    
    def __init__(self):
        self.birth_date = None
        self.birth_time = None
        self.gender = None
        self.lunar_date = None
        
    def set_birth_info(self, year: int, month: int, day: int, hour: int, minute: int, gender: str):
        """设置出生信息"""
        self.birth_date = datetime.datetime(year, month, day)
        self.birth_time = datetime.time(hour, minute)
        self.gender = gender
        
        # 这里应该转换为农历，简化起见使用公历
        self.lunar_date = {
            'year': year,
            'month': month,
            'day': day,
            'hour': hour
        }
        
    def calculate_ming_gong(self) -> int:
        """计算命宫位置"""
        # 简化算法：根据出生月份和时辰计算
        # 实际算法更复杂，这里使用简化版本
        month = self.lunar_date['month']
        hour = self.lunar_date['hour']
        
        # 简化算法：命宫 = (月份 + 时辰) % 12
        ming_gong = (month + hour) % 12
        return ming_gong if ming_gong != 0 else 12
    
    def calculate_shen_gong(self) -> int:
        """计算身宫位置"""
        # 简化算法：身宫 = (月份 + 时辰 + 6) % 12
        month = self.lunar_date['month']
        hour = self.lunar_date['hour']
        
        shen_gong = (month + hour + 6) % 12
        return shen_gong if shen_gong != 0 else 12
    
    def calculate_ziwei_star(self) -> int:
        """计算紫微星位置"""
        # 简化算法：根据农历日期计算
        day = self.lunar_date['day']
        
        # 简化算法：紫微星位置 = (日 + 5) % 12
        ziwei_pos = (day + 5) % 12
        return ziwei_pos if ziwei_pos != 0 else 12
    
    def arrange_palaces(self) -> List[Dict]:
        """排列十二宫"""
        ming_gong = self.calculate_ming_gong()
        palaces = []
        
        # 从命宫开始逆时针排列十二宫
        for i in range(12):
            palace_idx = (ming_gong - 1 - i) % 12
            if palace_idx < 0:
                palace_idx += 12
                
            palace = {
                'index': i + 1,
                'name': self.PALACES[palace_idx],
                'position': palace_idx + 1,
                'stars': []
            }
            palaces.append(palace)
            
        return palaces
    
    def arrange_stars(self, palaces: List[Dict]) -> List[Dict]:
        """安星（排列星曜）"""
        ziwei_pos = self.calculate_ziwei_star()
        
        # 简化安星算法
        for i, palace in enumerate(palaces):
            # 安紫微星系
            if (i + 1) == ziwei_pos:
                palace['stars'].append("紫微")
                
            # 安天府星系（简化：天府在紫微的对宫）
            tianfu_pos = (ziwei_pos + 6) % 12
            if tianfu_pos == 0:
                tianfu_pos = 12
            if (i + 1) == tianfu_pos:
                palace['stars'].append("天府")
                
            # 随机添加一些辅星（简化）
            if (i + 1) % 3 == 0:
                palace['stars'].append("左辅")
            if (i + 1) % 4 == 0:
                palace['stars'].append("文昌")
                
        return palaces
    
    def calculate_four_transformations(self) -> Dict[str, str]:
        """计算四化星"""
        # 简化算法：根据天干计算
        year = self.lunar_date['year']
        heavenly_stem = year % 10  # 简化：取年份个位数
        
        # 四化表（简化）
        transformations = {
            0: {"禄": "破军", "权": "武曲", "科": "太阳", "忌": "巨门"},
            1: {"禄": "武曲", "权": "太阳", "科": "天同", "忌": "太阴"},
            2: {"禄": "太阳", "权": "天同", "科": "天机", "忌": "巨门"},
            3: {"禄": "天同", "权": "天机", "科": "文昌", "忌": "廉贞"},
            4: {"禄": "廉贞", "权": "天梁", "科": "天相", "忌": "破军"},
            5: {"禄": "天府", "权": "紫微", "科": "文昌", "忌": "廉贞"},
            6: {"禄": "天机", "权": "文昌", "科": "天梁", "忌": "文曲"},
            7: {"禄": "天同", "权": "天机", "科": "文昌", "忌": "廉贞"},
            8: {"禄": "武曲", "权": "紫微", "科": "左辅", "忌": "右弼"},
            9: {"禄": "太阳", "权": "武曲", "科": "太阴", "忌": "天同"}
        }
        
        return transformations.get(heavenly_stem % 10, transformations[0])
    
    def calculate(self) -> Dict:
        """计算完整的紫微斗数命盘"""
        if not self.birth_date:
            raise ValueError("请先设置出生信息")
            
        # 计算命宫、身宫
        ming_gong = self.calculate_ming_gong()
        shen_gong = self.calculate_shen_gong()
        
        # 排列十二宫
        palaces = self.arrange_palaces()
        
        # 安星
        palaces = self.arrange_stars(palaces)
        
        # 计算四化
        four_transformations = self.calculate_four_transformations()
        
        # 构建命盘结果
        result = {
            'birth_info': {
                'date': self.birth_date.strftime('%Y-%m-%d'),
                'time': self.birth_time.strftime('%H:%M'),
                'gender': self.gender
            },
            'ming_gong': ming_gong,
            'shen_gong': shen_gong,
            'ziwei_position': self.calculate_ziwei_star(),
            'palaces': palaces,
            'four_transformations': four_transformations,
            'calculated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return result
    
    def print_chart(self, result: Dict):
        """打印命盘"""
        print("=" * 60)
        print("紫微斗数命盘")
        print("=" * 60)
        
        # 打印出生信息
        birth_info = result['birth_info']
        print(f"出生日期: {birth_info['date']} {birth_info['time']}")
        print(f"性别: {birth_info['gender']}")
        print(f"命宫: 第{result['ming_gong']}宫")
        print(f"身宫: 第{result['shen_gong']}宫")
        print(f"紫微星位置: 第{result['ziwei_position']}宫")
        
        print("\n" + "-" * 60)
        print("十二宫星曜分布:")
        print("-" * 60)
        
        for palace in result['palaces']:
            stars_str = "、".join(palace['stars']) if palace['stars'] else "无主星"
            print(f"{palace['position']:2d}. {palace['name']:8s} : {stars_str}")
            
        print("\n" + "-" * 60)
        print("四化星:")
        print("-" * 60)
        four_trans = result['four_transformations']
        print(f"化禄: {four_trans.get('禄', '未知')}")
        print(f"化权: {four_trans.get('权', '未知')}")
        print(f"化科: {four_trans.get('科', '未知')}")
        print(f"化忌: {four_trans.get('忌', '未知')}")
        
        print("\n" + "=" * 60)
        print(f"计算时间: {result['calculated_at']}")
        print("=" * 60)


def main():
    """主函数"""
    print("紫微斗数排盘程序")
    print("请输入出生信息:")
    
    try:
        # 获取用户输入
        year = int(input("出生年份 (如: 1990): "))
        month = int(input("出生月份 (1-12): "))
        day = int(input("出生日期 (1-31): "))
        hour = int(input("出生时辰 (0-23): "))
        minute = int(input("出生分钟 (0-59): "))
        gender = input("性别 (男/女): ")
        
        # 创建计算器
        calculator = ZiWeiCalculator()
        calculator.set_birth_info(year, month, day, hour, minute, gender)
        
        # 计算命盘
        print("\n正在计算命盘...")
        result = calculator.calculate()
        
        # 打印结果
        calculator.print_chart(result)
        
        # 询问是否保存结果
        save = input("\n是否保存结果到文件? (y/n): ")
        if save.lower() == 'y':
            filename = f"ziwei_chart_{year}{month:02d}{day:02d}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"结果已保存到: {filename}")
            
    except ValueError as e:
        print(f"输入错误: {e}")
    except Exception as e:
        print(f"计算错误: {e}")


if __name__ == "__main__":
    main()