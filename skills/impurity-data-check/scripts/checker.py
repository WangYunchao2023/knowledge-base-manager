#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPLC有关物质检测数据明显错误检查器
版本: 0.8.0
功能：批号格式一致性检查、忽略不计判断校验、支持按杂质名称配置不同报告限

支持阈值配置方式（优先级从高到低）：
1. 命令行 --threshold 参数（全局单一阈值）
2. 配置文件 impurity-checker.yaml（支持按杂质名称设置不同阈值）
3. Excel 表头自动识别
4. 内置默认值 0.05%
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
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_config_file(excel_path: str) -> Optional[str]:
    """优先查找 skill 目录的配置文件"""
    skill_config = os.path.join(SKILL_DIR, 'impurity-checker.yaml')
    if os.path.exists(skill_config):
        return skill_config
    return None


def load_config(excel_path: str) -> Dict:
    """加载配置文件，返回完整配置字典"""
    config_path = find_config_file(excel_path)
    if not config_path:
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config or {}
    except Exception as e:
        print(f"  ⚠️ 配置文件读取失败 ({config_path}): {e}")
        return {}


# ─────────────────────────────────────────────────────────────────
# 阈值解析（支持项目级配置 + 杂质级阈值）
# ─────────────────────────────────────────────────────────────────
class ThresholdResolver:
    """
    阈值解析器
    支持：
    - 项目级覆盖 project_overrides（每个项目可有独立 default_threshold + impurity_thresholds）
    - 杂质级阈值 impurity_thresholds（全局默认，按杂质名称模糊匹配）
    - default_threshold：全局默认阈值
    """

    def __init__(self, config: Dict, project_cfg: Optional[Dict] = None):
        self.config = config
        # 项目级配置（字典格式：default_threshold + impurity_thresholds）
        self.project_cfg = project_cfg
        # 全局兜底
        self.default_threshold = float(
            config.get('default_threshold') or config.get('report_threshold') or 0.05
        )
        self.impurity_thresholds = config.get('impurity_thresholds', {})

    def get_active_project(self, excel_path: str, ws=None) -> Tuple[Optional[str], Optional[Dict]]:
        """
        检测当前文件匹配哪个项目，返回 (项目关键词, 项目配置字典)
        搜索范围：文件名 > 路径 > Excel文件内容（前35行）
        """
        project_configs = self.config.get('project_configs', {})
        if not project_configs:
            return None, None

        excel_name = os.path.basename(excel_path)
        excel_dir = os.path.dirname(os.path.abspath(excel_path))

        # 1. 先从文件名/路径匹配
        for keyword, proj_cfg in project_configs.items():
            if keyword in excel_name or keyword in excel_dir:
                return keyword, proj_cfg if isinstance(proj_cfg, dict) else None

        # 2. 从 Excel 内容（前35行）匹配
        if ws is not None:
            content_texts = []
            for row in ws.iter_rows(min_row=1, max_row=35):
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        content_texts.append(cell.value.strip())
            full_text = '\n'.join(content_texts)
            for keyword, proj_cfg in project_configs.items():
                if keyword in full_text:
                    return keyword, proj_cfg if isinstance(proj_cfg, dict) else None

        return None, None

    def get_threshold(self, impurity_name: str) -> float:
        """
        根据杂质名称获取对应阈值
        匹配规则：精确匹配 > 包含匹配
        """
        # 优先使用项目级配置
        if self.project_cfg:
            project_impurities = self.project_cfg.get('impurity_thresholds', {})
            if project_impurities:
                for key, val in project_impurities.items():
                    if key == impurity_name:
                        return float(val)
                for key, val in project_impurities.items():
                    if key in impurity_name:
                        return float(val)
        # 兜底全局配置
        if self.impurity_thresholds:
            for key, val in self.impurity_thresholds.items():
                if key == impurity_name:
                    return float(val)
            for key, val in self.impurity_thresholds.items():
                if key in impurity_name:
                    return float(val)
        # 使用 default_threshold（优先项目级，其次全局）
        if self.project_cfg:
            return float(self.project_cfg.get('default_threshold', self.default_threshold))
        return self.default_threshold

    def get_default_threshold(self) -> float:
        """获取默认阈值（优先项目级）"""
        if self.project_cfg:
            return float(self.project_cfg.get('default_threshold', self.default_threshold))
        return self.default_threshold

    def resolve(self, excel_path: str, active_project: Optional[str] = None) -> Tuple[float, List[str]]:
        lines = []
        config_path = find_config_file(excel_path)
        if config_path:
            lines.append(f"📎 配置文件: {config_path}")

        if active_project and self.project_cfg:
            lines.append(f"📎 匹配项目: {active_project}")
            proj_default = self.project_cfg.get('default_threshold', self.default_threshold)
            lines.append(f"📎 项目默认报告限: {proj_default}%")
            proj_impurities = self.project_cfg.get('impurity_thresholds', {})
            if proj_impurities:
                lines.append(f"📎 项目杂质阈值: {len(proj_impurities)} 项")
                for name, val in list(proj_impurities.items())[:5]:
                    lines.append(f"    · {name} → {val}%")
                if len(proj_impurities) > 5:
                    lines.append(f"    · ... 共 {len(proj_impurities)} 项")
        else:
            lines.append(f"📎 默认报告限: {self.default_threshold}%")
            if self.impurity_thresholds:
                lines.append(f"📎 杂质专用阈值: {len(self.impurity_thresholds)} 项")
                for name, val in list(self.impurity_thresholds.items())[:5]:
                    lines.append(f"    · {name} → {val}%")
                if len(self.impurity_thresholds) > 5:
                    lines.append(f"    · ... 共 {len(self.impurity_thresholds)} 项")

        return self.get_default_threshold(), lines


# ─────────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────────
@dataclass
class CheckError:
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
        batch = batch.strip()
        if self.is_valid(batch):
            return batch
        match = re.match(r'^(.+)-(\d{8})$', batch)
        if match:
            prefix, digits = match.group(1), match.group(2)
            if digits.isdigit():
                return f"{prefix}-{digits[:6]}-{digits[6:8]}"
        return None


# ─────────────────────────────────────────────────────────────────
# 合并单元格解析器
# ─────────────────────────────────────────────────────────────────
class MergedCellResolver:
    def __init__(self, ws):
        self.ws = ws
        self.master_map: Dict[str, str] = {}
        for merged_range in ws.merged_cells.ranges:
            min_row, min_col, max_row, max_col = merged_range.bounds
            master_ref = f"{get_column_letter(min_col)}{min_row}"
            for r in range(min_row, max_row + 1):
                for c in range(min_col, max_col + 1):
                    self.master_map[f"{get_column_letter(c)}{r}"] = master_ref

    def get_master(self, cell_ref: str) -> str:
        return self.master_map.get(cell_ref, cell_ref)

    def is_merged(self, cell_ref: str) -> bool:
        return self.get_master(cell_ref) != cell_ref

    def get_merged_range_cells(self, master_ref: str) -> List[str]:
        return [ref for ref, m in self.master_map.items() if m == master_ref]

    def format_cell_ref(self, cell_ref: str) -> str:
        master = self.get_master(cell_ref)
        if self.is_merged(cell_ref):
            merged_cells = self.get_merged_range_cells(master)
            return self._format_range(merged_cells)
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
# 忽略不计检查器（支持按杂质名称动态阈值）
# ─────────────────────────────────────────────────────────────────
class IgnoreTermChecker:
    """
    忽略不计判断检查器
    支持按杂质名称设置不同报告限
    """

    def __init__(self, threshold_resolver: ThresholdResolver):
        self.resolver = threshold_resolver
        self.IGNORE_KW = ['忽略不计', '忽略', '不及']
        # (含量值字符串, 单元格引用, 杂质名称)
        self.detected: List[Tuple[str, str, str]] = []

    def check(self, content_value, report_value: str, cell_ref: str, impurity_name: str = ''):
        is_ignored = any(kw in str(report_value) for kw in self.IGNORE_KW)
        if is_ignored:
            self.detected.append((str(content_value), cell_ref, impurity_name))

    def final_check(self, resolver: MergedCellResolver) -> List[CheckError]:
        errors = []
        seen_masters = set()

        for content_str, cell_ref, impurity_name in self.detected:
            numbers = re.findall(r'[\d.]+', content_str)
            if not numbers:
                continue
            try:
                num_value = float(numbers[0])
            except ValueError:
                continue

            # 按杂质名称获取对应阈值
            threshold = self.resolver.get_threshold(impurity_name)

            if num_value >= threshold:
                master = resolver.get_master(cell_ref)
                is_merged = resolver.is_merged(cell_ref)

                if is_merged:
                    if master in seen_masters:
                        continue
                    seen_masters.add(master)
                    formatted = resolver.format_cell_ref(cell_ref)
                else:
                    formatted = resolver.format_cell_ref(cell_ref)

                impurity_info = f'（{impurity_name}）' if impurity_name else ''
                errors.append(CheckError(
                    cell_refs=formatted,
                    field='忽略不计',
                    current_values=f'{num_value}%{impurity_info} / "忽略不计"',
                    error_type='IGNORE_TERMS_WRONG',
                    message=f'含量{num_value}% ≥ 报告限{threshold}%{impurity_info}，不应标记为"忽略不计"',
                    suggestion=f'移除"忽略不计"标记，或确认该杂质的报告限标准'
                ))

        return errors


# ─────────────────────────────────────────────────────────────────
# 列结构识别（扩展：识别杂质名称列）
# ─────────────────────────────────────────────────────────────────
def find_columns(ws) -> List[Dict]:
    """
    识别表格列结构，返回多个可能的列配置
    每项包含：content_col（含量列）, report_col（报告值列）, name_col（杂质名称列）, start_row
    """
    results = []

    for row_idx in range(1, min(35, ws.max_row + 1)):
        for col_idx in range(1, ws.max_column + 1):
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if not cell_value:
                continue
            value = str(cell_value).strip()

            # 识别"含量（%）"列
            if '含量' in value and '%' in value:
                name_col = None
                # 在同一行向前查找"杂质名称"或"名称"列
                for offset in range(1, 6):
                    prev_cell = ws.cell(row=row_idx, column=col_idx - offset)
                    if prev_cell.value:
                        prev_val = str(prev_cell.value).strip()
                        if '杂质名称' in prev_val or prev_val == '名称':
                            name_col = col_idx - offset
                            break
                    prev_cell_right = ws.cell(row=row_idx, column=col_idx + offset)
                    if prev_cell_right.value:
                        prev_val_r = str(prev_cell_right.value).strip()
                        if '杂质名称' in prev_val_r:
                            name_col = col_idx + offset
                            break

                results.append({
                    'content_col': col_idx,
                    'report_col': col_idx + 1,
                    'name_col': name_col,
                    'start_row': row_idx + 1,
                })

    # 去重
    unique = []
    seen = set()
    for r in results:
        key = (r['content_col'], r['report_col'])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique if unique else [{'content_col': None, 'report_col': None, 'name_col': None, 'start_row': 1}]


def auto_detect_threshold_from_excel(ws) -> Optional[float]:
    """从 Excel 表头区域自动识别报告限值"""
    keywords = [
        r'报告限[：:\s]*([\d.]+)%',
        r'报告阈值[：:\s]*([\d.]+)%',
        r'报告限值[：:\s]*([\d.]+)%',
        r'定量限[：:\s]*([\d.]+)%',
        r'report\s*limit[：:\s]*([\d.]+)%',
        r'report\s*threshold[：:\s]*([\d.]+)%',
    ]

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
                        if 0 < val < 100:
                            print(f"  🔍 自动识别报告限: {val}% (来源: {cell.coordinate})")
                            return val
                    except ValueError:
                        pass
    return None


# ─────────────────────────────────────────────────────────────────
# 主检查函数
# ─────────────────────────────────────────────────────────────────
def check_file(file_path: str,
               batch_format: Optional[BatchFormatValidator] = None,
               cli_threshold: Optional[float] = None) -> Tuple[List[CheckError], ThresholdResolver]:
    if batch_format is None:
        batch_format = BatchFormatValidator()

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        print(f"❌ 无法打开文件：{e}")
        return [], ThresholdResolver({})

    ws = wb.active
    sections = find_columns(ws)
    resolver = MergedCellResolver(ws)

    # ── 确定阈值解析器 ──
    if cli_threshold is not None:
        # CLI 全局阈值模式
        config = {'default_threshold': cli_threshold, 'impurity_thresholds': {}}
        threshold_resolver = ThresholdResolver(config)
        print(f"  🎯 命令行指定报告限: {cli_threshold}%")
    else:
        config = load_config(file_path)
        if not config:
            auto_val = auto_detect_threshold_from_excel(ws)
            config = {'default_threshold': auto_val or 0.05, 'impurity_thresholds': {}}
            threshold_resolver = ThresholdResolver(config)
            print(f"  📌 使用内置默认报告限: 0.05%")
        else:
            # 检查是否有项目级配置
            resolver_for_proj = ThresholdResolver(config)
            active_project, project_cfg = resolver_for_proj.get_active_project(file_path, ws)
            threshold_resolver = ThresholdResolver(config, project_cfg)
            _, info_lines = threshold_resolver.resolve(file_path, active_project)
            for line in info_lines:
                print(f"  {line}")

    batch_checker = BatchNumberChecker(batch_format)
    ignore_checker = IgnoreTermChecker(threshold_resolver)

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

                            # 获取杂质名称
                            impurity_name = ''
                            if section.get('name_col'):
                                name_cell = ws.cell(row=cell.row, column=section['name_col'])
                                if name_cell.value:
                                    impurity_name = str(name_cell.value).strip()

                            ignore_checker.check(cell.value, report_val, cell_ref, impurity_name)

    wb.close()

    errors = []
    errors.extend(batch_checker.final_check(resolver))
    errors.extend(ignore_checker.final_check(resolver))

    return errors, threshold_resolver


# ─────────────────────────────────────────────────────────────────
# 输出格式化
# ─────────────────────────────────────────────────────────────────
def print_results(file_path: str, errors: List[CheckError], resolver: ThresholdResolver):
    basename = os.path.basename(file_path)

    if not errors:
        print(f"📋 {basename}")
        print(f"  ✅ 未发现明显错误")
        return

    header = f"📋 {basename}\n"
    header += f"  ⚠️ 发现 {len(errors)} 个潜在问题\n"
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
        description='HPLC有关物质检测数据明显错误检查器（支持按杂质名称配置报告限）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
阈值确定优先级（从高到低）：
  1. --threshold 参数（全局单一阈值）
  2. impurity-checker.yaml 配置文件
  3. Excel 表头自动识别
  4. 默认值 0.05%

impurity-checker.yaml 示例：
  # 默认报告限
  default_threshold: 0.05

  # 按杂质名称设置不同报告限
  impurity_thresholds:
    "杂质M": 0.03
    "杂质N": 0.10
    "其他单个杂质": 0.05
'''
    )
    parser.add_argument('file', nargs='?', help='待检查的 Excel 文件路径')
    parser.add_argument('--threshold', '-t', type=float, default=None,
                        help='指定全局报告限阈值（%%），如 --threshold 0.05')
    parser.add_argument('--version', '-v', action='version', version='%(prog)s 0.8.0')

    args = parser.parse_args()

    if not args.file:
        parser.print_help()
        sys.exit(1)

    file_path = args.file
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在：{file_path}")
        sys.exit(1)

    errors, resolver = check_file(file_path, cli_threshold=args.threshold)
    print_results(file_path, errors, resolver)


if __name__ == '__main__':
    main()
