"""
格式化输出模块
格式化统计字符串和打印统计表格
"""
from typing import Any, Dict, Tuple

from utils.accuracy_calculator import calculate_accuracy_value
from utils.constants import (
    FIELD_CORRECT,
    FIELD_MCQ_ACCURACY,
    FIELD_MCQ_CORRECT,
    FIELD_MCQ_TOTAL,
    FIELD_NUMERIC_ACCURACY,
    FIELD_NUMERIC_CORRECT,
    FIELD_NUMERIC_TOTAL,
    FIELD_TOTAL,
    FIELD_YESNO_ACCURACY,
    FIELD_YESNO_CORRECT,
    FIELD_YESNO_TOTAL,
    NUMBER_WIDTH,
    PATH_NAME_WIDTH,
    SEPARATOR_WIDTH,
)


def format_stat_string(
    correct: int,
    total: int,
    accuracy: float
) -> str:
    """
    格式化统计字符串：正确数/总数 (正确率%)
    
    Args:
        correct: 正确数量
        total: 总数量
        accuracy: 正确率（0.0 到 1.0）
        
    Returns:
        格式化后的字符串，格式为 "正确数/总数 (正确率%)"，
        如果总数为0则返回 "-"
    """
    if total > 0:
        return f"{correct}/{total} ({accuracy*100:.2f}%)"
    return "-"


def print_statistics_table(
    stats_by_path: Dict[str, Dict[str, Any]]
) -> Tuple[int, int]:
    """
    打印统计信息表格（五栏：增强路径、选择题、Yes/No、数值、总计）
    
    Args:
        stats_by_path: 按路径类型的统计字典
        
    Returns:
        (总正确数, 总数量) 元组
    """
    print("=" * SEPARATOR_WIDTH)
    print("各增强路径的正确率统计")
    print("=" * SEPARATOR_WIDTH)
    print(
        f"{'增强路径':<{PATH_NAME_WIDTH}} {'选择题':<{NUMBER_WIDTH}} "
        f"{'Yes/No':<{NUMBER_WIDTH}} {'数值':<{NUMBER_WIDTH}} "
        f"{'总计':<{NUMBER_WIDTH}}"
    )
    print("-" * SEPARATOR_WIDTH)
    
    # 累计总计
    totals = {
        FIELD_CORRECT: 0,
        FIELD_TOTAL: 0,
        FIELD_MCQ_CORRECT: 0,
        FIELD_MCQ_TOTAL: 0,
        FIELD_YESNO_CORRECT: 0,
        FIELD_YESNO_TOTAL: 0,
        FIELD_NUMERIC_CORRECT: 0,
        FIELD_NUMERIC_TOTAL: 0
    }
    
    # 打印各路径的统计
    for path_type in sorted(stats_by_path.keys()):
        stats = stats_by_path[path_type]
        
        # 累计总计
        for key in totals:
            totals[key] += stats[key]
        
        # 格式化并打印
        mcq_str = format_stat_string(
            stats[FIELD_MCQ_CORRECT],
            stats[FIELD_MCQ_TOTAL],
            stats.get(FIELD_MCQ_ACCURACY, 0.0)
        )
        yesno_str = format_stat_string(
            stats[FIELD_YESNO_CORRECT],
            stats[FIELD_YESNO_TOTAL],
            stats.get(FIELD_YESNO_ACCURACY, 0.0)
        )
        numeric_str = format_stat_string(
            stats[FIELD_NUMERIC_CORRECT],
            stats[FIELD_NUMERIC_TOTAL],
            stats.get(FIELD_NUMERIC_ACCURACY, 0.0)
        )
        total_str = format_stat_string(
            stats[FIELD_CORRECT],
            stats[FIELD_TOTAL],
            stats.get('accuracy', 0.0)
        )
        
        print(
            f"{path_type:<{PATH_NAME_WIDTH}} {mcq_str:<{NUMBER_WIDTH}} "
            f"{yesno_str:<{NUMBER_WIDTH}} {numeric_str:<{NUMBER_WIDTH}} "
            f"{total_str:<{NUMBER_WIDTH}}"
        )
    
    # 打印总计行
    print("-" * SEPARATOR_WIDTH)
    if totals[FIELD_TOTAL] > 0:
        overall_accuracy = calculate_accuracy_value(
            totals[FIELD_CORRECT], totals[FIELD_TOTAL]
        )
        mcq_overall_accuracy = calculate_accuracy_value(
            totals[FIELD_MCQ_CORRECT], totals[FIELD_MCQ_TOTAL]
        )
        yesno_overall_accuracy = calculate_accuracy_value(
            totals[FIELD_YESNO_CORRECT], totals[FIELD_YESNO_TOTAL]
        )
        numeric_overall_accuracy = calculate_accuracy_value(
            totals[FIELD_NUMERIC_CORRECT], totals[FIELD_NUMERIC_TOTAL]
        )
        
        mcq_str = format_stat_string(
            totals[FIELD_MCQ_CORRECT],
            totals[FIELD_MCQ_TOTAL],
            mcq_overall_accuracy
        )
        yesno_str = format_stat_string(
            totals[FIELD_YESNO_CORRECT],
            totals[FIELD_YESNO_TOTAL],
            yesno_overall_accuracy
        )
        numeric_str = format_stat_string(
            totals[FIELD_NUMERIC_CORRECT],
            totals[FIELD_NUMERIC_TOTAL],
            numeric_overall_accuracy
        )
        total_str = format_stat_string(
            totals[FIELD_CORRECT],
            totals[FIELD_TOTAL],
            overall_accuracy
        )
        
        print(
            f"{'总计':<{PATH_NAME_WIDTH}} {mcq_str:<{NUMBER_WIDTH}} "
            f"{yesno_str:<{NUMBER_WIDTH}} {numeric_str:<{NUMBER_WIDTH}} "
            f"{total_str:<{NUMBER_WIDTH}}"
        )
    print("=" * SEPARATOR_WIDTH)
    
    return totals[FIELD_CORRECT], totals[FIELD_TOTAL]
