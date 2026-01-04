"""
统计管理模块
创建和管理统计条目，更新统计信息
"""
from collections import defaultdict
from typing import Any, Dict, Optional

from utils.constants import (
    FIELD_CORRECT,
    FIELD_CORRECT_LINE_NUMBERS,
    FIELD_INCORRECT_LINE_NUMBERS,
    FIELD_LINE_NUMBERS,
    FIELD_MCQ_CORRECT,
    FIELD_MCQ_TOTAL,
    FIELD_NONMCQ_CORRECT,
    FIELD_NONMCQ_TOTAL,
    FIELD_NUMERIC_CORRECT,
    FIELD_NUMERIC_TOTAL,
    FIELD_TOTAL,
    FIELD_YESNO_CORRECT,
    FIELD_YESNO_TOTAL,
    NONMCQ_TYPE_NUMERIC,
    NONMCQ_TYPE_YESNO,
)


def create_default_stat_entry() -> Dict[str, Any]:
    """
    创建默认的统计条目
    
    Returns:
        包含所有统计字段的默认字典
    """
    return {
        FIELD_CORRECT: 0,
        FIELD_TOTAL: 0,
        'accuracy': 0.0,
        FIELD_LINE_NUMBERS: [],
        FIELD_CORRECT_LINE_NUMBERS: [],
        FIELD_INCORRECT_LINE_NUMBERS: [],
        FIELD_MCQ_CORRECT: 0,
        FIELD_MCQ_TOTAL: 0,
        FIELD_NONMCQ_CORRECT: 0,
        FIELD_NONMCQ_TOTAL: 0,
        FIELD_YESNO_CORRECT: 0,
        FIELD_YESNO_TOTAL: 0,
        FIELD_NUMERIC_CORRECT: 0,
        FIELD_NUMERIC_TOTAL: 0
    }


def update_statistics(
    stats_by_path: Dict[str, Dict[str, Any]],
    path_type: str,
    line_in_dataset: int,
    is_correct: bool,
    is_mcq: Optional[bool] = None,
    nonmcq_type: Optional[str] = None
) -> None:
    """
    更新统计信息
    
    Args:
        stats_by_path: 按路径类型的统计字典
        path_type: 增强路径类型
        line_in_dataset: 数据集中的行号
        is_correct: 是否正确
        is_mcq: 是否为选择题（True=选择题，False=填空题，None=未知）
        nonmcq_type: 填空题类型（'yesno'=Yes/No类型，'numeric'=数值类型，
        None=未知或其他）
    """
    if path_type not in stats_by_path:
        stats_by_path[path_type] = create_default_stat_entry()
    
    stats = stats_by_path[path_type]
    stats[FIELD_TOTAL] += 1
    stats[FIELD_LINE_NUMBERS].append(line_in_dataset)
    
    if is_correct:
        stats[FIELD_CORRECT] += 1
        stats[FIELD_CORRECT_LINE_NUMBERS].append(line_in_dataset)
    else:
        stats[FIELD_INCORRECT_LINE_NUMBERS].append(line_in_dataset)
    
    # 更新选择题/填空题统计
    if is_mcq is not None:
        if is_mcq:
            stats[FIELD_MCQ_TOTAL] += 1
            if is_correct:
                stats[FIELD_MCQ_CORRECT] += 1
        else:
            stats[FIELD_NONMCQ_TOTAL] += 1
            if is_correct:
                stats[FIELD_NONMCQ_CORRECT] += 1
            
            # 更新填空题子类型统计
            if nonmcq_type == NONMCQ_TYPE_YESNO:
                stats[FIELD_YESNO_TOTAL] += 1
                if is_correct:
                    stats[FIELD_YESNO_CORRECT] += 1
            elif nonmcq_type == NONMCQ_TYPE_NUMERIC:
                stats[FIELD_NUMERIC_TOTAL] += 1
                if is_correct:
                    stats[FIELD_NUMERIC_CORRECT] += 1


def create_stats_dict() -> Dict[str, Dict[str, Any]]:
    """
    创建统计字典
    
    Returns:
        使用defaultdict创建的统计字典
    """
    return defaultdict(create_default_stat_entry)
