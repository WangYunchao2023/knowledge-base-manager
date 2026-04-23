#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPLC有关物质检测数据明显错误检查器
版本: 0.4.0
功能：批号格式一致性检查、忽略不计判断校验
"""

import re
import os
import sys
from typing import List, Dict, Tuple, Optional, Set
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
    cell_refs: str          # 合并后的单元格引用，如 "A27,B31" 或 "A-C/21-23"
    field: str
    current_values: str     # 第一个值作为代表
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
        """检查批号是否符合标准格式"""
        if not batch:
            return False
        return self._compiled.match(batch.strip()) is not None

    def normalize(self, batch: str) -> Optional[str]:
        """
        将非标准格式批号标准化
        例如：LMS002-26040105 → LMS002-260401-05
        """
        batch = batch.strip()
        if self.is_valid(batch):
            return batch

        # 尝试：LMS002-26040105（无连字符）→ LMS002-260401-05
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
        # 构建映射：单元格 -> 主单元格
        self.master_map: Dict[str, str] = {}
        self.merged_ranges: List[Tuple[int, int, int, int]] = []

        for merged_range in ws.merged_cells.ranges:
            min_row, min_col, max_row, max_col = merged_range.bounds
            self.merged_ranges.append((min_row, min_col, max_row, max_col))
            # 所有单元格映射到左上角主单元格
            master_ref = f"{get_column_letter(min_col)}{min_row}"
            for r in range(min_row, max_row + 1):
                for c in range(min_col, max_col + 1):
                    self.master_map[f"{get_column_letter(c)}{r}"] = master_ref

    def get_master(self, cell_ref: str) -> str:
        """获取单元格的主引用（处理合并单元格）"""
        return self.master_map.get(cell_ref, cell_ref)

    def format_ranges(self, cell_refs: List[str]) -> str:
        """
        格式化单元格引用列表
        合并的单元格用 A-C/21-23 格式
        同一主单元格的多个引用合并显示
        """
        if not cell_refs:
            return ""

        # 先将所有引用归一化到主单元格
        masters = [self.get_master(ref) for ref in cell_refs]
        unique_masters = list(set(masters))

        # 按行列分组
        row_groups: Dict[int, List[str]] = defaultdict(list)
        for ref in unique_masters:
            match = re.match(r'([A-Z]+)(\d+)', ref)
            if match:
                col, row = match.group(1), int(match.group(2))
                row_groups[row].append(col)

        # 格式化输出
        parts = []
        for row in sorted(row_groups.keys()):
            cols = sorted(row_groups[row])
            if len(cols) == 1:
                parts.append(f"{cols[0]}{row}")
            elif self._is_consecutive_cols(cols):
                # 连续的列，合并显示如 A-C/21
                parts.append(f"{cols[0]}-{cols[-1]}/{row}")
            else:
                # 不连续，用逗号分隔
                parts.append(f"{','.join(cols)}/{row}")

        return ", ".join(parts)

    def _is_consecutive_cols(self, cols: List[str]) -> bool:
        """检查列是否是连续的"""
        col_nums = [ord(c) - ord('A') for c in cols]
        col_nums.sort()
        for i in range(1, len(col_nums)):
            if col_nums[i] - col_nums[i-1] != 1:
                return False
        return True


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
        # 存储检测到的批号：(值, [单元格列表])
        self.detected: Dict[str, List[str]] = defaultdict(list)

    def _strip_suffix(self, value: str) -> str:
        """去除批号后的复测/再测等备注"""
        for suffix in ['（复测）', '(复测)', '（再测）', '(再测)']:
            if suffix in value:
                return value.split(suffix)[0].strip()
        return value.strip()

    def _is_batch_like(self, value: str) -> bool:
        """判断是否像批号"""
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

        # 批号必须包含字母
        if not any(c.isalpha() for c in value):
            return False

        return True

    def check(self, cell_ref: str, value: str):
        """收集批号信息"""
        if not self._is_batch_like(value):
            return

        self.detected[value].append(cell_ref)

    def final_check(self) -> List[CheckError]:
        """
        最终检查：批号格式一致性
        逻辑：找到所有不符合标准格式的批号，按值分组报告
        """
        errors = []

        # 分类：符合格式的 vs 不符合格式的
        valid_batches = {}  # {标准化的值: [原始值列表]}
        invalid_batches = {}  # {原始值: [单元格列表]}

        for raw_value, cell_refs in self.detected.items():
            batch_body = self._strip_suffix(raw_value)

            if self.batch_format.is_valid(batch_body):
                continue

            normalized = self.batch_format.normalize(batch_body)
            if not normalized:
                continue

            # 记录这个不符合格式的批号
            invalid_batches[raw_value] = (normalized, cell_refs)

        if not invalid_batches:
            return errors

        # 找到文件中最多的有效格式作为参考
        valid_ref = None
        for raw_value, cell_refs in self.detected.items():
            batch_body = self._strip_suffix(raw_value)
            if self.batch_format.is_valid(batch_body):
                valid_ref = batch_body
                break

        # 为每个不符合格式的批号生成错误报告
        for raw_value, (normalized, cell_refs) in invalid_batches.items():
            # 还原后缀
            batch_body = self._strip_suffix(raw_value)
            if batch_body != raw_value:
                suffix = raw_value[len(batch_body):]
                normalized += suffix

            errors.append(CheckError(
                cell_refs="未确定",  # 先用placeholder
                field='批号格式',
                current_values=raw_value,
                error_type='BATCH_FORMAT_INVALID',
                message=f'批号格式不符合标准（{self.batch_format.pattern_desc}）',
                suggestion=normalized
            ))

        return errors

    def merge_duplicate_errors(self, errors: List[CheckError]) -> List[CheckError]:
        """
        合并同一错误值的重复检测
        例如：LMS002-26040105 出现在 A27 和 B31，应合并为一条错误
        """
        merged = {}

        for err in errors:
            if err.current_values in merged:
                # 合并单元格引用
                existing = merged[err.current_values]
                existing.cell_refs = err.cell_refs  # cell_refs will be set later
            else:
                merged[err.current_values] = err

        return list(merged.values())


class IgnoreTermChecker:
    """忽略不计判断检查器"""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.IGNORE_KW = ['忽略不计', '忽略', '不及']
        self.detected: Dict[str, List[str]] = defaultdict(list)

    def check(self, content_value, report_value: str, cell_ref: str):
        """收集忽略不计信息"""
        is_ignored = any(kw in str(report_value) for kw in self.IGNORE_KW)
        if is_ignored:
            self.detected[str(content_value)].append(cell_ref)

    def final_check(self) -> List[CheckError]:
        """
        检查忽略不计标记是否合理
        逻辑：标记"忽略不计"的含量值必须 < 阈值
        """
        errors = []

        for content_str, cell_refs in self.detected.items():
            # 提取数值
            numbers = re.findall(r'[\d.]+', content_str)
            if not numbers:
                continue
            try:
                num_value = float(numbers[0])
            except ValueError:
                continue

            if num_value >= self.threshold:
                errors.append(CheckError(
                    cell_refs="未确定",
                    field='忽略不计',
                    current_values=f'{num_value}% / "忽略不计"',
                    error_type='IGNORE_TERMS_WRONG',
                    message=f'含量{num_value}% ≥ 阈值{self.threshold}%，不应标记为"忽略不计"',
                    suggestion=f'移除"忽略不计"标记，或确认阈值标准'
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

            # 找含量列
            if '含量' in value and '%' in value:
                report_col = col_idx + 1  # 报告值在含量列右边
                results.append({
                    'content_col': col_idx,
                    'report_col': report_col,
                    'start_row': row_idx + 1,
                })

    # 去重（同一列配置只保留一个）
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
    """检查整个文件"""
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

    # 扫描所有单元格
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue

            value = str(cell.value).strip()
            cell_ref = cell.coordinate

            # 批号检查
            batch_checker.check(cell_ref, value)

            # 忽略不计检查（遍历所有找到的列配置）
            for section in sections:
                if section['content_col'] and section['report_col']:
                    if cell.column == section['content_col'] and cell.row >= section['start_row']:
                        if cell.value is not None:
                            report_cell = ws.cell(row=cell.row, column=cell.column + 1)
                            report_val = str(report_cell.value) if report_cell.value else ''
                            ignore_checker.check(cell.value, report_val, cell_ref)

    wb.close()

    # 最终检查
    errors = []
    errors.extend(batch_checker.final_check())
    errors.extend(ignore_checker.final_check())

    # 合并重复检测（同一错误值只报一次，但保留所有单元格位置）
    final_errors = []
    for err in errors:
        # 获取所有实际单元格引用
        if err.field == '批号格式':
            cells = batch_checker.detected.get(err.current_values, [])
        elif err.field == '忽略不计':
            # 从 current_values 提取数值找检测结果
            num_match = re.search(r'([\d.]+)%', err.current_values)
            if num_match:
                num_str = num_match.group(1)
                cells = ignore_checker.detected.get(num_str, [])
            else:
                cells = []
        else:
            cells = []

        # 格式化单元格引用
        formatted_refs = resolver.format_ranges(cells)
        if not formatted_refs:
            # 如果找不到，用原始检测的第一个作为代表
            if err.field == '批号格式' and batch_checker.detected:
                sample_cells = list(batch_checker.detected.values())[0]
                formatted_refs = resolver.format_ranges(sample_cells[:2])
            else:
                formatted_refs = "（请手动检查）"

        err.cell_refs = formatted_refs
        final_errors.append(err)

    return final_errors


def print_results(file_path: str, errors: List[CheckError]):
    """打印检查结果"""
    print(f"\n📋 检查报告：{os.path.basename(file_path)}")
    print("=" * 50)

    if not errors:
        print("✅ 未发现明显错误")
        return

    print(f"⚠️ 发现 {len(errors)} 个潜在问题\n")
    for e in errors:
        print(f"[{e.field}] {e.cell_refs} | {e.current_values}")
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