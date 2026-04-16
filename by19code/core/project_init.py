"""BY19Code 项目初始化模块

负责在项目首次使用时生成 BY19Code.md 文件。
"""
from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_by19code_md(project_root: Path, project_name: str) -> None:
    """生成 BY19Code.md 项目约束文件。

    参数
    ----
    project_root : 项目根目录
    project_name : 项目名称
    """
    by19code_md_path = project_root / "BY19Code.md"

    # 如果文件已存在，不覆盖
    if by19code_md_path.exists():
        logger.debug("[项目初始化] BY19Code.md 已存在，跳过生成")
        return

    # 生成模板内容
    content = f"""# {project_name} - BY19Code 项目约束

> 本文件由 BY19Code 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 用于记录项目的设计约束、开发规范和架构决策

## 项目信息

- **项目名称**: {project_name}
- **项目路径**: {project_root}
- **创建时间**: {datetime.now().strftime('%Y-%m-%d')}

## 技术栈

请在此处记录项目使用的技术栈：

- 编程语言：
- 框架/库：
- 数据库：
- 其他工具：

## 开发规范

### 代码规范

- 代码风格：
- 命名规范：
- 注释要求：

### 文件组织

- 目录结构：
- 文件命名：

## 架构设计

### 系统架构

请在此处描述系统的整体架构：

### 模块划分

请在此处描述各模块的职责：

## 开发约束

### 必须遵守的规则

1.
2.
3.

### 禁止的操作

1.
2.
3.

## API 设计

### RESTful API 规范

-
-

### 数据格式

-

## 数据库设计

### 表结构

请在此处记录数据库表结构：

### 索引策略

-

## 测试要求

### 单元测试

- 覆盖率要求：
- 测试框架：

### 集成测试

-

## 部署说明

### 环境要求

-

### 部署流程

1.
2.
3.

## 变更记录

### {datetime.now().strftime('%Y-%m-%d')}

- 项目初始化
- 创建 BY19Code.md 文件

---

**注意**: 本文件应随项目演进持续更新，记录所有重要的设计决策和约束条件。
"""

    # 写入文件
    try:
        by19code_md_path.write_text(content, encoding="utf-8")
        logger.info("[项目初始化] 已生成 BY19Code.md: %s", by19code_md_path)
    except Exception as e:
        logger.error("[项目初始化] 生成 BY19Code.md 失败: %s", e)


def check_and_init_project(project_root: Path) -> None:
    """检查并初始化项目。

    如果项目根目录下不存在 BY19Code.md，则自动生成。

    参数
    ----
    project_root : 项目根目录
    """
    project_name = project_root.name
    generate_by19code_md(project_root, project_name)
