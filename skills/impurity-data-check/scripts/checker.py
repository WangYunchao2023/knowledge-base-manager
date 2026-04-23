#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPLC有关物质检测数据明显错误检查器
版本: 0.1.0
功能：批号格式检查、忽略不计判断检查
"""

import re
import os
import sys
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("❌ 需要 openpyxl，请运行: pip install openpyxl")
    sys.exit(1)


@dataclass
class CheckError:
    """检查错误"""
    cell_ref: str
    field: str
    current_value: str
    error_type: str
    message: str
    suggestion: str

    def __str__(self):
        return (f"[{self.field}] {self.cell_ref} | {self.current_value}\n"
                f"  问题：{self.message}\n"
                f"  建议：{self.suggestion}")


class BatchNumberChecker:
    """批号格式检查器"""

    def __init__(self):
        self.found_batches: List[str] = []
        self.batch_patterns: Set[str] = set()  # 存储不同格式类型

    def parse_batch(self, value: str) -> Optional[Dict]:
        """解析批号，返回结构化信息"""
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        # 排除明显不是批号的内容
        non_batch_keywords = ['对照品', '系统适应性', '灵敏度', '流动相', '稀释', '空白',
                              '溶剂', '配制', '来源', '对照', '自身', '杂质', '名称',
                              '供试品名称', '批号', '样品', '实验日期', '检验人', '复核人',
                              '检查（有关物质）', '检查（含量）']
        for kw in non_batch_keywords:
            if kw in value:
                return None

        # 排除纯数字序号（1, 2, 3...）
        if re.match(r'^\d+$', value):
            return None

        # 排除文件路径、URL
        if '://' in value or '/' in value or '\\' in value:
            return None

        # 查找类似批号的模式
        # LMS002-260401-05, LMS00226040105, Y0001665
        match = re.match(r'^([A-Z]+\d*[A-Z]*)-?(\d{6,8})?-?(\d*).*', value)
        if match:
            prefix = match.group(1)
            date_part = match.group(2) if match.group(2) else ''
            seq_part = match.group(3) if match.group(3) else ''

            if len(prefix) >= 3 and (date_part or seq_part):
                return {
                    'prefix': prefix,
                    'date_part': date_part,
                    'seq_part': seq_part,
                    'raw': value,
                    'has_dash': '-' in value[:10] if len(value) > 10 else False,
                }

        return None

    def extract_batch_number(self, value: str) -> Optional[str]:
        """从字符串中提取批号"""
        parsed = self.parse_batch(value)
        if parsed:
            return parsed['raw']
        return None

    def check_consistency(self, cell_ref: str, value: str) -> Optional[CheckError]:
        """检查同一文件内批号格式一致性"""
        parsed = self.parse_batch(value)
        if not parsed:
            return None

        self.found_batches.append(parsed['raw'])

        # 空格检查
        if ' ' in value and '（' not in value and '(' not in value:
            # 有空格但不在括号旁，可能是错误
            pass
        if ' ' in value:
            fixed = value.replace(' ', '').replace('（', '(').replace('）', ')')
            # 规范化空格
            if '  ' in fixed:
                fixed = re.sub(r'\s+', '', fixed)

        # 空格检查（已禁用，按需启用）
        # if ' ' in value:
        #     fixed = value.replace(' ', '')
        #     return CheckError(...)

        return None

    def final_consistency_check(self) -> List[CheckError]:
        """最终一致性检查（所有数据收集完后调用）"""
        errors = []

        if len(self.found_batches) < 2:
            return errors

        # 解析所有批号格式
        parsed_batches = []
        for b in self.found_batches:
            p = self.parse_batch(b)
            if p:
                parsed_batches.append(p)

        if len(parsed_batches) < 2:
            return errors

        # 检查日期部分的位数一致性
        # LMS002-26040105 (date_part=26040105, 8位)
        # LMS002-260401-06 (date_part=260401, 6位; seq_part=06)

        date_lengths = set()
        for p in parsed_batches:
            if p['date_part']:
                date_lengths.add(len(p['date_part']))

        # 如果日期部分位数不一致，说明格式不统一
        if len(date_lengths) > 1:
            # 找出所有不统一的批号
            for p in parsed_batches:
                if len(p['date_part']) == 8:  # 8位格式，需要补连字符
                    prefix = p['prefix']
                    date = p['date_part'][:6]
                    seq = p['date_part'][6:]
                    fixed = f"{prefix}-{date}"
                    if seq:
                        fixed += f"-{seq}"
                    return [CheckError(
                        cell_ref='',  # 需要外部传入
                        field='批号格式',
                        current_value=p['raw'],
                        error_type='BATCH_INCONSISTENT',
                        message='批号格式与文件内其他批号不一致',
                        suggestion=f'建议：{fixed}'
                    )]

        return errors


class IgnoreTermChecker:
    """忽略不计判断检查器"""

    # 忽略不计的阈值（企业标准，通常0.05%或0.10%）
    DEFAULT_THRESHOLD = 0.05

    # 允许标记"忽略不计"的关键词
    IGNORE_KEYWORDS = ['忽略不计', '忽略', '不计']

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold

    def check(self, content_value: str, report_value: str, cell_ref: str) -> Optional[CheckError]:
        """
        检查忽略不计标记是否正确

        参数：
            content_value: 含量数值（字符串）
            report_value: 报告值/备注栏内容
            cell_ref: 单元格引用
        """
        # 检查是否标记了"忽略不计"
        is_ignored = False
        for kw in self.IGNORE_KEYWORDS:
            if kw in str(report_value):
                is_ignored = True
                break

        if not is_ignored:
            return None

        # 提取数值
        if isinstance(content_value, (int, float)):
            num_value = float(content_value)
        else:
            # 从字符串中提取数字
            numbers = re.findall(r'[\d.]+', str(content_value))
            if not numbers:
                return None
            try:
                num_value = float(numbers[0])
            except ValueError:
                return None

        # 检查数值是否真的应该忽略不计
        if num_value >= self.threshold:
            return CheckError(
                cell_ref=cell_ref,
                field='忽略不计',
                current_value=f'{num_value}% / "{report_value}"',
                error_type='IGNORE_TERMS_WRONG',
                message=f'含量{num_value}% ≥ 阈值{self.threshold}%，不应标记为"忽略不计"',
                suggestion=f'移除"忽略不计"标记，或确认阈值标准'
            )

        return None


def find_data_section(ws) -> Dict:
    """
    尝试识别表格的数据区域
    返回：{
        'batch_col': 批号列索引,
        'content_col': 含量列索引,
        'report_col': 报告值列索引,
        'start_row': 数据起始行,
    }
    """
    result = {
        'batch_col': None,
        'content_col': None,
        'report_col': None,
        'start_row': 1,
    }

    # 扫描前20行找表头
    for row_idx in range(1, min(21, ws.max_row + 1)):
        for col_idx in range(1, ws.max_column + 1):
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if not cell_value:
                continue

            value = str(cell_value).strip()

            # 找批号列
            if result['batch_col'] is None:
                if '批号' in value or 'Batch' in value or 'Lot' in value:
                    result['batch_col'] = col_idx
                    result['start_row'] = row_idx + 1

            # 找含量列（已知杂质的含量）
            if result['content_col'] is None:
                if '含量' in value and '%' in value:
                    result['content_col'] = col_idx

            # 找报告值列
            if result['report_col'] is None:
                if '报告值' in value or ('%' in value and '忽略' in value):
                    result['report_col'] = col_idx

    # 如果没找到报告值列，尝试在含量列右边找
    if result['report_col'] is None and result['content_col'] is not None:
        result['report_col'] = result['content_col'] + 1

    return result


def check_file(file_path: str) -> List[CheckError]:
    """检查整个文件"""
    errors: List[CheckError] = []

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        print(f"❌ 无法打开文件：{e}")
        return errors

    ws = wb.active

    # 识别表格结构
    section = find_data_section(ws)

    batch_checker = BatchNumberChecker()
    ignore_checker = IgnoreTermChecker()

    # 扫描所有单元格
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue

            value = str(cell.value).strip()

            # 批号检查
            batch_error = batch_checker.check_consistency(cell.coordinate, value)
            if batch_error:
                errors.append(batch_error)

            # 忽略不计检查（只在数据区域）
            if section['content_col'] and section['report_col']:
                col = cell.column
                row_num = cell.row

                # 检查含量列
                if col == section['content_col'] and row_num >= section['start_row']:
                    content_val = cell.value
                    # 报告值在右边一列
                    report_cell = ws.cell(row=row_num, column=col + 1)
                    report_val = str(report_cell.value) if report_cell.value else ''

                    ignore_error = ignore_checker.check(content_val, report_val, cell.coordinate)
                    if ignore_error:
                        errors.append(ignore_error)

    wb.close()

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    # 收集所有批号进行一致性检查
    batch_checker = BatchNumberChecker()

    for row in ws.iter_rows():
        for cell in row:
            if cell.value:
                batch_checker.check_consistency(cell.coordinate, str(cell.value))

    # 执行最终一致性检查
    consistency_errors = batch_checker.final_consistency_check()
    for e in consistency_errors:
        errors.append(e)

    wb.close()

    return errors


def print_results(file_path: str, errors: List[CheckError]):
    """打印检查结果"""
    print(f"\n📋 检查报告：{os.path.basename(file_path)}")
    print("=" * 50)

    if not errors:
        print("✅ 未发现明显错误")
        return

    print(f"⚠️ 发现 {len(errors)} 个潜在问题\n")

    # 按错误类型分组
    batch_errors = [e for e in errors if '批号' in e.field]
    ignore_errors = [e for e in errors if '忽略不计' in e.field]

    for e in batch_errors:
        print(f"[批号格式] {e.cell_ref} | {e.current_value}")
        print(f"  问题：{e.message}")
        print(f"  建议：{e.suggestion}")
        print()

    for e in ignore_errors:
        print(f"[忽略不计] {e.cell_ref}")
        print(f"  当前：{e.current_value}")
        print(f"  问题：{e.message}")
        print(f"  建议：{e.suggestion}")
        print()


def main():
    if len(sys.argv) < 2:
        print("用法: python checker.py <Excel文件路径>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在：{file_path}")
        sys.exit(1)

    errors = check_file(file_path)
    print_results(file_path, errors)


if __name__ == '__main__':
    main()
