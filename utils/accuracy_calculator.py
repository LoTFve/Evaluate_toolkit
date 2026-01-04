"""
正确率计算模块
计算单条记录和整体统计的正确率
"""
from typing import Any, Dict

from utils.constants import (
    FIELD_ACCURACY,
    FIELD_CORRECT,
    FIELD_MCQ_ACCURACY,
    FIELD_MCQ_CORRECT,
    FIELD_MCQ_TOTAL,
    FIELD_NONMCQ_ACCURACY,
    FIELD_NONMCQ_CORRECT,
    FIELD_NONMCQ_TOTAL,
    FIELD_NUMERIC_ACCURACY,
    FIELD_NUMERIC_CORRECT,
    FIELD_NUMERIC_TOTAL,
    FIELD_TOTAL,
    FIELD_YESNO_ACCURACY,
    FIELD_YESNO_CORRECT,
    FIELD_YESNO_TOTAL,
)

# 从根目录导入 eval_output
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from eval_output import process_line as eval_process_line


def calculate_accuracy(
    record: Dict[str, Any],
    line_in_dataset: int
) -> float:
    """
    计算记录的正确率
    
    Args:
        record: 记录字典
        line_in_dataset: 数据集中的行号
        
    Returns:
        正确率（0.0 到 1.0）
    """
    try:
        accuracy, _ = eval_process_line(record)
        return accuracy
    except Exception as e:
        print(
            f"警告: 计算正确率时出错 "
            f"(lineInDataset: {line_in_dataset}): {e}"
        )
        return 0.0


def calculate_accuracy_value(correct: int, total: int) -> float:
    """
    计算正确率
    
    Args:
        correct: 正确数量
        total: 总数量
        
    Returns:
        正确率（0.0 到 1.0），如果总数为0则返回0.0
    """
    return correct / total if total > 0 else 0.0


def calculate_path_accuracies(
    stats_by_path: Dict[str, Dict[str, Any]]
) -> None:
    """
    计算各路径的正确率
    
    Args:
        stats_by_path: 按路径类型的统计字典
    """
    for stats in stats_by_path.values():
        stats[FIELD_ACCURACY] = calculate_accuracy_value(
            stats[FIELD_CORRECT], stats[FIELD_TOTAL]
        )
        stats[FIELD_MCQ_ACCURACY] = calculate_accuracy_value(
            stats[FIELD_MCQ_CORRECT], stats[FIELD_MCQ_TOTAL]
        )
        stats[FIELD_NONMCQ_ACCURACY] = calculate_accuracy_value(
            stats[FIELD_NONMCQ_CORRECT], stats[FIELD_NONMCQ_TOTAL]
        )
        stats[FIELD_YESNO_ACCURACY] = calculate_accuracy_value(
            stats[FIELD_YESNO_CORRECT], stats[FIELD_YESNO_TOTAL]
        )
        stats[FIELD_NUMERIC_ACCURACY] = calculate_accuracy_value(
            stats[FIELD_NUMERIC_CORRECT], stats[FIELD_NUMERIC_TOTAL]
        )
