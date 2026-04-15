#!/usr/bin/env python3
"""
ls.py - 模拟 Linux ls 命令，打印当前目录下的文件和目录
"""

import os
import sys
from pathlib import Path


def list_directory(path=".", show_all=False, long_format=False):
    """
    列出指定目录下的文件和目录
    
    Args:
        path: 目录路径，默认为当前目录
        show_all: 是否显示隐藏文件（以点开头的文件）
        long_format: 是否显示详细信息
    """
    try:
        # 获取目录路径
        dir_path = Path(path)
        if not dir_path.exists():
            print(f"错误: 目录 '{path}' 不存在")
            return 1
        
        if not dir_path.is_dir():
            print(f"错误: '{path}' 不是目录")
            return 1
        
        # 获取目录内容
        items = []
        for item in dir_path.iterdir():
            # 如果不显示隐藏文件，跳过以点开头的文件
            if not show_all and item.name.startswith('.'):
                continue
            items.append(item)
        
        # 按名称排序
        items.sort(key=lambda x: x.name.lower())
        
        # 显示结果
        if long_format:
            # 长格式显示
            for item in items:
                # 获取文件信息
                stat = item.stat()
                # 判断类型
                if item.is_dir():
                    file_type = 'd'
                elif item.is_file():
                    file_type = '-'
                elif item.is_symlink():
                    file_type = 'l'
                else:
                    file_type = '?'
                
                # 权限（简化版）
                mode = stat.st_mode
                perms = ''
                for who in "USR", "GRP", "OTH":
                    for what in "R", "W", "X":
                        if mode & getattr(os, f"S_I{what}{who}"):
                            perms += what.lower()
                        else:
                            perms += '-'
                
                # 大小
                size = stat.st_size
                
                # 修改时间
                import time
                mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(stat.st_mtime))
                
                # 显示
                print(f"{file_type}{perms} {size:8d} {mtime} {item.name}")
        else:
            # 简单格式显示
            for item in items:
                if item.is_dir():
                    print(f"{item.name}/")
                else:
                    print(item.name)
        
        return 0
        
    except PermissionError:
        print(f"错误: 没有权限访问目录 '{path}'")
        return 1
    except Exception as e:
        print(f"错误: {e}")
        return 1


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="列出目录内容",
        epilog="示例: python ls.py -a -l"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="要列出的目录路径（默认为当前目录）"
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="显示所有文件，包括隐藏文件"
    )
    parser.add_argument(
        "-l", "--long",
        action="store_true",
        help="使用长格式显示详细信息"
    )
    
    args = parser.parse_args()
    
    # 执行目录列表
    return list_directory(args.path, args.all, args.long)


if __name__ == "__main__":
    sys.exit(main())