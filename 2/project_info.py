#!/usr/bin/env python3
"""
项目信息查看脚本
"""

import os
import sys
import platform
import json

def get_project_info():
    """获取项目信息"""
    info = {
        "project_path": os.getcwd(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "files": [],
        "directories": []
    }
    
    # 列出当前目录内容
    for item in os.listdir('.'):
        item_path = os.path.join('.', item)
        if os.path.isfile(item_path):
            info["files"].append(item)
        elif os.path.isdir(item_path):
            info["directories"].append(item)
    
    return info

def main():
    """主函数"""
    print("=== 项目信息 ===")
    info = get_project_info()
    
    print(f"项目路径: {info['project_path']}")
    print(f"Python版本: {info['python_version'].split()[0]}")
    print(f"操作系统: {info['platform']}")
    print(f"\n=== 目录内容 ===")
    
    if info['files']:
        print("文件:")
        for file in sorted(info['files']):
            print(f"  - {file}")
    
    if info['directories']:
        print("\n目录:")
        for dir in sorted(info['directories']):
            print(f"  - {dir}")
    
    print(f"\n总计: {len(info['files'])} 个文件, {len(info['directories'])} 个目录")

if __name__ == "__main__":
    main()