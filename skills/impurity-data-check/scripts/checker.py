#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPLC有关物质检测数据明显错误检查器
版本: 0.5.0
功能：批号格式一致性检查、忽略不计判断校验
"""

import re
import os
import sys
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

try:
    import openpyxl
    from openpyxl.utils import get_column_letter
except ImportError:
    print("❌ 需要 openpyxl，请运行: pip install openpyxl")
    sys.exit(1)


@dataclass
class CheckError:
    """检查错误"""
    cell_refs: str          # 单元格引用，如 "A27" 或 "A-C/21-23"（合并单元格）
    field: str
    current_values: str
    error_type: str
    message: str
    suggestion: str

    def __str__(self):
        return (f"[{self.field}] {self.cell_refs} | {self.current_values}\n"
                f"  问题：{self.message}\n"
                f"  建议：{self.suggestion}")


class BatchFormatValidator:
    """
    批号格式验证器
    标准格式：项目编号(可变长)-两位年两位月两位日-两位序号
    例如：LMS002-260401-05
    """

    def __init__(self,
                 pattern: str = r'^(.+)-(\d{2})(\d{2})(\d{2})-(\d{2})$',
                 pattern_desc: str = '项目编号-年月日-序号（例：LMS002-260401-05）'):
        self.pattern = pattern
        self.pattern_desc = pattern_desc
        self._compiled = re.compile(pattern)

    def is_valid(self, batch: str) -> bool:
        if not batch:
            return False
        return self._compiled.match(batch.strip()) is not None

    def normalize(self, batch: str) -> Optional[str]:
        """将非标准格式批号标准化，如 LMS002-26040105 → LMS002-260401-05"""
        batch = batch.strip()
        if self.is_valid(batch):
            return batch

        match = re.match(r'^(.+)-(\d{8})$', batch)
        if match:
            prefix = match.group(1)
            digits = match.group(2)
            if digits.isdigit():
                return f"{prefix}-{digits[:6]}-{digits[6:8]}"

        return None


class MergedCellResolver:
    """合并单元格解析器"""

    def __init__(self, ws):
        self.ws = ws
        self.master_map: Dict[str, str] = {}  # cell_ref -> master_ref
        self.merged_ranges: List[Tuple[int, int, int, int]] = []

        for merged_range in ws.merged_cells.ranges:
            min_row, min_col, max_row, max_col = merged_range.bounds
            self.merged_ranges.append((min_row, min_col, max_row, max_col))
            master_ref = f"{get_column_letter(min_col)}{min_row}"
            for r in range(min_row, max_row + 1):
                for c in range(min_col, max_col + 1):
                    self.master_map[f"{get_column_letter(c)}{r}"] = master_ref

    def get_master(self, cell_ref: str) -> str:
        return self.master_map.get(cell_ref, cell_ref)

    def is_merged(self, cell_ref: str) -> bool:
        return self.get_master(cell_ref) != cell_ref

    def get_merged_range_cells(self, master_ref: str) -> List[str]:
        """获取属于同一个合并区域的所有单元格"""
        result = []
        for ref, master in self.master_map.items():
            if master == master_ref:
                result.append(ref)
        return result

    def format_cell_ref(self, cell_ref: str) -> str:
        """格式化单元格引用"""
        master = self.get_master(cell_ref)

        if self.is_merged(cell_ref):
            # 是合并单元格，格式化整个合并区域
            merged_cells = self.get_merged_range_cells(master)
            return self._format_range(merged_cells)
        else:
            return cell_ref

    def _format_range(self, cell_refs: List[str]) -> str:
        """将单元格列表格式化为 A-C/21-23 格式"""
        if not cell_refs:
            return ""

        # 解析并分组
        parsed = []
        for ref in cell_refs:
            m = re.match(r'([A-Z]+)(\d+)', ref)
            if m:
                parsed.append((m.group(1), int(m.group(2))))

        if not parsed:
            return ", ".join(cell_refs)

        # 按行分组
        row_groups: Dict[int, List[str]] = defaultdict(list)
        for col, row in parsed:
            row_groups[row].append(col)

        parts = []
        for row in sorted(row_groups.keys()):
            cols = sorted(row_groups[row], key=lambda c: ord(c[0]))
            if len(cols) == 1:
                parts.append(f"{cols[0]}{row}")
            elif self._is_consecutive(cols):
                parts.append(f"{cols[0]}-{cols[-1]}/{row}")
            else:
                parts.append(f"{','.join(cols)}/{row}")

        return ", ".join(parts)

    def _is_consecutive(self, cols: List[str]) -> bool:
        nums = sorted([ord(c) - ord('A') for c in cols])
        return all(nums[i+1] - nums[i] == 1 for i in range(len(nums) - 1))


class BatchNumberChecker:
    """批号格式一致性检查器"""

    NON_BATCH_KEYWORDS = [
        '对照品', '系统适应性', '灵敏度', '流动相', '稀释', '空白',
        '溶剂', '配制', '来源', '对照', '自身', '杂质', '名称',
        '供试品名称', '批号', '样品', '实验日期', '检验人', '复核人',
        '实验员', '检测项目', '数据存储路径', '方法', '仪器',
        '泵模块', '进样器模块', '柱温箱模块', '检测器模块',
        '理论塔板数', '拖尾因子', '分离度', 'RSD', 'RSD%',
        '峰面积', '保留时间', '相对保留时间', '信噪比',
        '供试品', '灵敏度溶液', '系统适用性', '计算公式',
    ]

    def __init__(self, batch_format: BatchFormatValidator):
        self.batch_format = batch_format
        self.detected: List[Tuple[str, str]] = []  # (值, 单元格引用)

    def _strip_suffix(self, value: str) -> str:
        for suffix in ['（复测）', '(复测)', '（再测）', '(再测)']:
            if suffix in value:
                return value.split(suffix)[0].strip()
        return value.strip()

    def _is_batch_like(self, value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        value = value.strip()
        for kw in self.NON_BATCH_KEYWORDS:
            if kw in value:
                return False
        if re.match(r'^\d+$', value):
            return False
        if '://' in value or ('/' in value and not '-' in value):
            return False
        if not any(c.isalpha() for c in value):
            return False
        return True

    def check(self, cell_ref: str, value: str):
        if self._is_batch_like(value):
            self.detected.append((value, cell_ref))

    def final_check(self, resolver: MergedCellResolver) -> List[CheckError]:
        """
        逐个单元格报告错误
        合并单元格中的错误 → 合并为一个引用
        独立单元格中的错误 → 各自报告
        """
        errors = []
        seen_masters = set()  # 已报告过的合并区域主单元格

        for raw_value, cell_ref in self.detected:
            batch_body = self._strip_suffix(raw_value)

            if self.batch_format.is_valid(batch_body):
                continue

            normalized = self.batch_format.normalize(batch_body)
            if not normalized:
                continue

            if batch_body != raw_value:
                normalized += raw_value[len(batch_body):]

            master = resolver.get_master(cell_ref)
            is_merged = resolver.is_merged(cell_ref)

            if is_merged:
                # 合并单元格：已报告过则跳过
                if master in seen_masters:
                    continue
                seen_masters.add(master)
                formatted = resolver.format_cell_ref(cell_ref)
            else:
                # 独立单元格：直接报告
                formatted = resolver.format_cell_ref(cell_ref)

            errors.append(CheckError(
                cell_refs=formatted,
                field='批号格式',
                current_values=raw_value,
                error_type='BATCH_FORMAT_INVALID',
                message=f'批号格式不符合标准（{self.batch_format.pattern_desc}）',
                suggestion=normalized
            ))

        return errors


class IgnoreTermChecker:
    """忽略不计判断检查器"""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.IGNORE_KW = ['忽略不计', '忽略', '不及']
        self.detected: List[Tuple[str, str]] = []  # (含量值字符串, 单元格引用)

    def check(self, content_value, report_value: str, cell_ref: str):
        is_ignored = any(kw in str(report_value) for kw in self.IGNORE_KW)
        if is_ignored:
            self.detected.append((str(content_value), cell_ref))

    def final_check(self, resolver: MergedCellResolver) -> List[CheckError]:
        """
        逐个单元格报告忽略不计错误
        合并单元格中的错误 → 合并为一个引用
        """
        errors = []
        seen_masters = set()

        for content_str, cell_ref in self.detected:
            numbers = re.findall(r'[\d.]+', content_str)
            if not numbers:
                continue
            try:
                num_value = float(numbers[0])
            except ValueError:
                continue

            if num_value >= self.threshold:
                master = resolver.get_master(cell_ref)
                is_merged = resolver.is_merged(cell_ref)

                if is_merged:
                    if master in seen_masters:
                        continue
                    seen_masters.add(master)
                    formatted = resolver.format_cell_ref(cell_ref)
                else:
                    formatted = resolver.format_cell_ref(cell_ref)

                errors.append(CheckError(
                    cell_refs=formatted,
                    field='忽略不计',
                    current_values=f'{num_value}% / "忽略不计"',
                    error_type='IGNORE_TERMS_WRONG',
                    message=f'含量{num_value}% ≥ 阈值{self.threshold}%，不应标记为"忽略不计"',
                    suggestion='移除"忽略不计"标记，或确认阈值标准'
                ))

        return errors


def find_columns(ws) -> List[Dict]:
    """识别表格列结构，返回多个可能的列配置"""
    results = []

    for row_idx in range(1, min(35, ws.max_row + 1)):
        for col_idx in range(1, ws.max_column + 1):
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if not cell_value:
                continue
            value = str(cell_value).strip()

            if '含量' in value and '%' in value:
                results.append({
                    'content_col': col_idx,
                    'report_col': col_idx + 1,
                    'start_row': row_idx + 1,
                })

    unique = []
    seen = set()
    for r in results:
        key = (r['content_col'], r['report_col'])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique if unique else [{'content_col': None, 'report_col': None, 'start_row': 1}]


def check_file(file_path: str,
               batch_format: Optional[BatchFormatValidator] = None,
               ignore_threshold: float = 0.05) -> List[CheckError]:
    if batch_format is None:
        batch_format = BatchFormatValidator()

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        print(f"❌ 无法打开文件：{e}")
        return []

    ws = wb.active
    sections = find_columns(ws)
    resolver = MergedCellResolver(ws)

    batch_checker = BatchNumberChecker(batch_format)
    ignore_checker = IgnoreTermChecker(threshold=ignore_threshold)

    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue

            value = str(cell.value).strip()
            cell_ref = cell.coordinate

            batch_checker.check(cell_ref, value)

            for section in sections:
                if section['content_col'] and section['report_col']:
                    if cell.column == section['content_col'] and cell.row >= section['start_row']:
                        if cell.value is not None:
                            report_cell = ws.cell(row=cell.row, column=cell.column + 1)
                            report_val = str(report_cell.value) if report_cell.value else ''
                            ignore_checker.check(cell.value, report_val, cell_ref)

    wb.close()

    errors = []
    errors.extend(batch_checker.final_check(resolver))
    errors.extend(ignore_checker.final_check(resolver))

    return errors


def print_results(file_path: str, errors: List[CheckError]):
    basename = os.path.basename(file_path)

    if not errors:
        print(f"📋 {basename}")
        print(f"  ⚠️ 发现 0 个潜在问题")
        return

    # 表头 - 宽度加宽
    header = f"📋 {basename}\n  ⚠️ 发现 {len(errors)} 个潜在问题\n"
    header += "┌──────────┬──────────┬──────────────────────────────────────────────────────────────┐\n"
    header += "│ 类型     │ 位置     │ 问题                                                           │\n"
    header += "├──────────┼──────────┼──────────────────────────────────────────────────────────────┤"


    print(header)


    for e in errors:
        print(f"│ {e.field:<8} │ {e.cell_refs:<8} │ {e.message:<60} │")

    print("└──────────┴──────────┴──────────────────────────────────────────────────────────────┘")


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
