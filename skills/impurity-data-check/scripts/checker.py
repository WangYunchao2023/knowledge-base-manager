#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPLC有关物质检测数据明显错误检查器
版本: 0.7.0
功能：批号格式一致性检查、忽略不计判断校验、报告限动态判断

支持三种阈值指定方式（优先级从高到低）：
1. 命令行 --threshold 参数
2. 被检文件同目录的 impurity-checker.yaml 配置文件
3. skill 目录的 impurity-checker.yaml 配置文件
4. 默认值 0.05%
"""

import re
import os
import sys
import yaml
import argparse
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

try:
    import openpyxl
    from openpyxl.utils import get_column_letter
except ImportError:
    print("❌ 需要 openpyxl，请运行: pip install openpyxl")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# 配置文件查找路径
# ─────────────────────────────────────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

def find_config_file(excel_path: str) -> Optional[str]:
    """按优先级查找配置文件"""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(excel_path)), 'impurity-checker.yaml'),
        os.path.join(SKILL_DIR, 'impurity-checker.yaml'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load_threshold_from_config(excel_path: str) -> Optional[float]:
    """从配置文件读取报告限阈值"""
    config_path = find_config_file(excel_path)
    if not config_path:
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        threshold = config.get('report_threshold') or config.get('threshold')
        if threshold is not None:
            val = float(threshold)
            print(f"  📎 配置文件: {config_path}")
            print(f"  📎 报告限: {val}%")
            return val
    except Exception as e:
        print(f"  ⚠️ 配置文件读取失败 ({config_path}): {e}")
    return None


def auto_detect_threshold_from_excel(ws) -> Optional[float]:
    """
    从 Excel 表头区域自动识别报告限值
    支持格式：
      报告限：0.05%
      报告限 0.05%
      报告阈值：0.05%
      报告阈值 0.05%
      报告限值 0.05%
      定量限 0.05%（也作为报告限参考）
    """
    keywords = [
        r'报告限[：:\s]*([\d.]+)%',
        r'报告阈值[：:\s]*([\d.]+)%',
        r'报告限值[：:\s]*([\d.]+)%',
        r'定量限[：:\s]*([\d.]+)%',
        r'report\s*limit[：:\s]*([\d.]+)%',
        r'report\s*threshold[：:\s]*([\d.]+)%',
    ]

    # 只扫描前 35 行（表头区域）
    for row in ws.iter_rows(min_row=1, max_row=35):
        for cell in row:
            if cell.value is None:
                continue
            text = str(cell.value).strip()
            for kw_pattern in keywords:
                m = re.search(kw_pattern, text, re.IGNORECASE)
                if m:
                    try:
                        val = float(m.group(1))
                        if 0 < val < 100:  # 合理范围
                            print(f"  🔍 自动识别报告限: {val}% (来源: {cell.coordinate})")
                            return val
                    except ValueError:
                        pass
    return None


# ─────────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────────
@dataclass
class CheckError:
    """检查错误"""
    cell_refs: str
    field: str
    current_values: str
    error_type: str
    message: str
    suggestion: str

    def __str__(self):
        return (f"[{self.field}] {self.cell_refs} | {self.current_values}\n"
                f"  问题：{self.message}\n"
                f"  建议：{self.suggestion}")


# ─────────────────────────────────────────────────────────────────
# 批号格式验证器
# ─────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────
# 合并单元格解析器
# ─────────────────────────────────────────────────────────────────
class MergedCellResolver:
    """合并单元格解析器"""

    def __init__(self, ws):
        self.ws = ws
        self.master_map: Dict[str, str] = {}
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
        result = []
        for ref, master in self.master_map.items():
            if master == master_ref:
                result.append(ref)
        return result

    def format_cell_ref(self, cell_ref: str) -> str:
        master = self.get_master(cell_ref)
        if self.is_merged(cell_ref):
            merged_cells = self.get_merged_range_cells(master)
            return self._format_range(merged_cells)
        else:
            return cell_ref

    def _format_range(self, cell_refs: List[str]) -> str:
        if not cell_refs:
            return ""
        parsed = []
        for ref in cell_refs:
            m = re.match(r'([A-Z]+)(\d+)', ref)
            if m:
                parsed.append((m.group(1), int(m.group(2))))
        if not parsed:
            return ", ".join(cell_refs)

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


# ─────────────────────────────────────────────────────────────────
# 批号格式检查器
# ─────────────────────────────────────────────────────────────────
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
        self.detected: List[Tuple[str, str]] = []

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
        errors = []
        seen_masters = set()

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
                if master in seen_masters:
                    continue
                seen_masters.add(master)
                formatted = resolver.format_cell_ref(cell_ref)
            else:
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


# ─────────────────────────────────────────────────────────────────
# 忽略不计检查器（支持动态阈值）
# ─────────────────────────────────────────────────────────────────
class IgnoreTermChecker:
    """
    忽略不计判断检查器
    支持动态阈值：可通过命令行 --threshold 或配置文件指定
    """

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.IGNORE_KW = ['忽略不计', '忽略', '不及']
        self.detected: List[Tuple[str, str]] = []

    def set_threshold(self, threshold: float):
        self.threshold = threshold

    def check(self, content_value, report_value: str, cell_ref: str):
        is_ignored = any(kw in str(report_value) for kw in self.IGNORE_KW)
        if is_ignored:
            self.detected.append((str(content_value), cell_ref))

    def final_check(self, resolver: MergedCellResolver) -> List[CheckError]:
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
                    message=f'含量{num_value}% ≥ 报告限{self.threshold}%，不应标记为"忽略不计"',
                    suggestion=f'移除"忽略不计"标记，或确认报告限标准'
                ))

        return errors


# ─────────────────────────────────────────────────────────────────
# 列结构识别
# ─────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────
# 主检查函数
# ─────────────────────────────────────────────────────────────────
def resolve_threshold(file_path: str, ws, cli_threshold: Optional[float]) -> float:
    """
    按优先级确定报告限阈值
    优先级：CLI参数 > 配置文件 > Excel自动识别 > 默认0.05%
    """
    if cli_threshold is not None:
        print(f"  🎯 命令行指定报告限: {cli_threshold}%")
        return cli_threshold

    config_threshold = load_threshold_from_config(file_path)
    if config_threshold is not None:
        return config_threshold

    auto_threshold = auto_detect_threshold_from_excel(ws)
    if auto_threshold is not None:
        return auto_threshold

    print(f"  📌 使用默认报告限: 0.05%")
    return 0.05


def check_file(file_path: str,
               batch_format: Optional[BatchFormatValidator] = None,
               ignore_threshold: Optional[float] = None) -> Tuple[List[CheckError], float]:
    """
    检查文件，返回 (错误列表, 使用的阈值)
    """
    if batch_format is None:
        batch_format = BatchFormatValidator()

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        print(f"❌ 无法打开文件：{e}")
        return [], 0.05

    ws = wb.active
    sections = find_columns(ws)

    # ── 确定阈值（优先级：CLI > 配置文件 > Excel自动识别 > 默认） ──
    threshold = resolve_threshold(file_path, ws, ignore_threshold)

    resolver = MergedCellResolver(ws)
    batch_checker = BatchNumberChecker(batch_format)
    ignore_checker = IgnoreTermChecker(threshold=threshold)

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

    return errors, threshold


# ─────────────────────────────────────────────────────────────────
# 输出格式化
# ─────────────────────────────────────────────────────────────────
def print_results(file_path: str, errors: List[CheckError], threshold: float):
    basename = os.path.basename(file_path)

    if not errors:
        print(f"📋 {basename}")
        print(f"  ✅ 未发现明显错误（报告限: {threshold}%）")
        return

    header = f"📋 {basename}  |  报告限: {threshold}%\n  ⚠️ 发现 {len(errors)} 个潜在问题\n"
    header += "┌──────────┬──────────┬──────────────────────────────────────────────────────────────┐\n"
    header += "│ 类型     │ 位置     │ 问题                                                           │\n"
    header += "├──────────┼──────────┼──────────────────────────────────────────────────────────────┤"

    print(header)

    for e in errors:
        print(f"│ {e.field:<8} │ {e.cell_refs:<8} │ {e.message:<60} │")

    print("└──────────┴──────────┴──────────────────────────────────────────────────────────────┘")


# ─────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='HPLC有关物质检测数据明显错误检查器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
阈值确定优先级（从高到低）：
  1. --threshold 参数
  2. 被检文件同目录 impurity-checker.yaml
  3. skill 目录 impurity-checker.yaml
  4. Excel 表头自动识别（报告限：X%）
  5. 默认值 0.05%%

impurity-checker.yaml 示例：
  report_threshold: 0.05   # 报告限，%% 可以省略
  # 或
  threshold: 0.05
'''
    )
    parser.add_argument('file', nargs='?', help='待检查的 Excel 文件路径')
    parser.add_argument('--threshold', '-t', type=float, default=None,
                        help='指定报告限阈值（%%），例如 --threshold 0.05')
    parser.add_argument('--version', '-v', action='version', version='%(prog)s 0.7.0')

    args = parser.parse_args()

    if not args.file:
        parser.print_help()
        sys.exit(1)

    file_path = args.file
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在：{file_path}")
        sys.exit(1)

    errors, threshold = check_file(file_path, ignore_threshold=args.threshold)
    print_results(file_path, errors, threshold)


if __name__ == '__main__':
    main()
