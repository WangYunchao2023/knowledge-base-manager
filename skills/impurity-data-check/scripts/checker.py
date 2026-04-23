#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPLC有关物质检测数据明显错误检查器
版本: 0.3.0
功能：批号格式一致性检查、忽略不计判断校验
"""

import re
import os
import sys
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

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


class BatchFormatValidator:
    """
    批号格式验证器
    标准格式：项目编号(可变长)-两位年两位月两位日-两位序号
    例如：LMS002-260401-05

    正则：^(.+)-(\d{2})(\d{2})(\d{2})-(\d{2})$
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
        格式：YYMMDDNN（年月日+序号各2位）
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
                # YYMMDDNN → YYMMDD-NN
                return f"{prefix}-{digits[:6]}-{digits[6:8]}"

        return None


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
        # 收集：(原始值, 单元格引用)
        self.found_batches: List[Tuple[str, str]] = []

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
        if '://' in value or '/' in value or '\\' in value:
            return False

        # 批号必须包含字母
        if not any(c.isalpha() for c in value):
            return False

        return True

    def check(self, cell_ref: str, value: str) -> Optional[CheckError]:
        """检查单个单元格的批号格式（是否符合标准格式）"""
        if not self._is_batch_like(value):
            return None

        self.found_batches.append((value, cell_ref))

        batch_body = self._strip_suffix(value)

        if not self.batch_format.is_valid(batch_body):
            normalized = self.batch_format.normalize(batch_body)
            if normalized:
                # 还原后缀
                if batch_body != value:
                    suffix = value[len(batch_body):]
                    normalized += suffix
                return CheckError(
                    cell_ref=cell_ref,
                    field='批号格式',
                    current_value=value,
                    error_type='BATCH_FORMAT_INVALID',
                    message=f'批号不符合标准格式（{self.batch_format.pattern_desc}）',
                    suggestion=normalized
                )

        return None

    def final_consistency_check(self) -> List[CheckError]:
        """
        一致性检查：同一文件内所有批号格式应统一
        逻辑：以文件中最多的有效格式为基准，报告其他不一致的批号
        """
        errors = []

        if len(self.found_batches) < 2:
            return errors

        # 分类：有效的 vs 无效的（格式层面）
        valid_ref = None  # 第一个符合标准格式的批号作为参考
        invalid_batches: List[Tuple[str, str]] = []

        for value, cell_ref in self.found_batches:
            batch_body = self._strip_suffix(value)
            if self.batch_format.is_valid(batch_body):
                if valid_ref is None:
                    valid_ref = (value, cell_ref)
            else:
                # 格式不符合，检查是否能通过补连字符修正
                if self.batch_format.normalize(batch_body):
                    invalid_batches.append((value, cell_ref))

        # 如果存在符合标准的批号，且有可修正的无效批号，报告一致性错误
        if valid_ref is None or not invalid_batches:
            return errors

        ref_value, ref_cell = valid_ref
        ref_body = self._strip_suffix(ref_value)

        for value, cell_ref in invalid_batches:
            batch_body = self._strip_suffix(value)
            normalized = self.batch_format.normalize(batch_body)
            if normalized and batch_body != value:
                suffix = value[len(batch_body):]
                normalized += suffix

            errors.append(CheckError(
                cell_ref=cell_ref,
                field='批号格式',
                current_value=value,
                error_type='BATCH_INCONSISTENT',
                message=f'批号格式与文件内其他批号不一致（参考：{ref_body}）',
                suggestion=normalized if normalized else value
            ))

        return errors


class IgnoreTermChecker:
    """忽略不计判断检查器"""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.IGNORE_KW = ['忽略不计', '忽略', '不计']

    def check(self, content_value, report_value: str, cell_ref: str) -> Optional[CheckError]:
        """检查忽略不计标记是否合理"""
        # 检查是否标记了"忽略不计"
        is_ignored = any(kw in str(report_value) for kw in self.IGNORE_KW)
        if not is_ignored:
            return None

        # 提取数值
        if isinstance(content_value, (int, float)):
            num_value = float(content_value)
        else:
            numbers = re.findall(r'[\d.]+', str(content_value))
            if not numbers:
                return None
            try:
                num_value = float(numbers[0])
            except ValueError:
                return None

        if num_value >= self.threshold:
            return CheckError(
                cell_ref=cell_ref,
                field='忽略不计',
                current_value=f'{num_value}% / "{report_value}"',
                error_type='IGNORE_TERMS_WRONG',
                message=f'含量{num_value}% ≥ 阈值{self.threshold}%，不应标记为"忽略不计"',
                suggestion='移除"忽略不计"标记，或确认阈值标准'
            )

        return None


def find_columns(ws) -> Dict:
    """识别表格列结构"""
    result = {'batch_col': None, 'content_col': None, 'report_col': None, 'start_row': 1}

    for row_idx in range(1, min(25, ws.max_row + 1)):
        for col_idx in range(1, ws.max_column + 1):
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if not cell_value:
                continue
            value = str(cell_value).strip()

            if result['batch_col'] is None and ('批号' in value or 'Batch' in value or 'Lot' in value):
                result['batch_col'] = col_idx
                result['start_row'] = row_idx + 1

            if result['content_col'] is None and '含量' in value and '%' in value:
                result['content_col'] = col_idx

            if result['report_col'] is None and ('报告值' in value or ('%' in value and ('忽略' in value or '不计' in value))):
                result['report_col'] = col_idx

    if result['report_col'] is None and result['content_col'] is not None:
        result['report_col'] = result['content_col'] + 1

    return result


def check_file(file_path: str,
               batch_format: Optional[BatchFormatValidator] = None,
               ignore_threshold: float = 0.05) -> List[CheckError]:
    """检查整个文件"""
    errors: List[CheckError] = []

    if batch_format is None:
        batch_format = BatchFormatValidator()

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        print(f"❌ 无法打开文件：{e}")
        return errors

    ws = wb.active
    section = find_columns(ws)

    batch_checker = BatchNumberChecker(batch_format)
    ignore_checker = IgnoreTermChecker(threshold=ignore_threshold)

    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue

            value = str(cell.value).strip()
            cell_ref = cell.coordinate

            # 批号格式检查
            batch_checker.check(cell_ref, value)

            # 忽略不计检查
            if section['content_col'] and section['report_col']:
                if cell.column == section['content_col'] and cell.row >= section['start_row']:
                    content_val = cell.value
                    if content_val is not None:
                        report_cell = ws.cell(row=cell.row, column=cell.column + 1)
                        report_val = str(report_cell.value) if report_cell.value else ''
                        err = ignore_checker.check(content_val, report_val, cell_ref)
                        if err:
                            errors.append(err)

    wb.close()

    # 一致性检查
    consistency_errors = batch_checker.final_consistency_check()
    errors.extend(consistency_errors)

    return errors


def print_results(file_path: str, errors: List[CheckError]):
    """打印检查结果"""
    print(f"\n📋 检查报告：{os.path.basename(file_path)}")
    print("=" * 50)

    if not errors:
        print("✅ 未发现明显错误")
        return

    print(f"⚠️ 发现 {len(errors)} 个潜在问题\n")
    for e in errors:
        print(f"[{e.field}] {e.cell_ref} | {e.current_value}")
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
