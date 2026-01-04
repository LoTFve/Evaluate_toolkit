"""
结果构建模块
创建结果记录和格式化答案
"""
from typing import Any, Dict, List, Optional

from utils.constants import (
    ANSWER_MAX_LENGTH,
    FIELD_ACCURACY,
    JSON_FIELD_ANSWER,
    JSON_FIELD_EXPECTED_ANSWER,
    JSON_FIELD_LINE_IN_DATASET,
    JSON_FIELD_TOOLS_USED,
    PATH_TYPE_TOOL,
)


def truncate_answer(
    answer: str,
    max_length: int = ANSWER_MAX_LENGTH
) -> str:
    """
    截断答案字符串（保留最后 N 个字符）
    
    Args:
        answer: 原始答案
        max_length: 最大长度
        
    Returns:
        截断后的答案
    """
    if len(answer) > max_length:
        return answer[-max_length:]
    return answer


def create_result_record(
    record: Dict[str, Any],
    path_type: str,
    accuracy: float,
    tools_used: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    创建结果记录
    
    Args:
        record: 原始记录
        path_type: 增强路径类型
        accuracy: 正确率
        tools_used: 使用的工具列表（可选）
        
    Returns:
        结果记录字典
    """
    result = {
        JSON_FIELD_LINE_IN_DATASET: record.get(
            JSON_FIELD_LINE_IN_DATASET, 0
        ),
        'enhancement_path': path_type,
        FIELD_ACCURACY: accuracy,
        'is_correct': accuracy == 1.0,
        JSON_FIELD_EXPECTED_ANSWER: record.get(
            JSON_FIELD_EXPECTED_ANSWER, ''
        ),
        JSON_FIELD_ANSWER: truncate_answer(
            record.get(JSON_FIELD_ANSWER, '')
        )
    }
    
    if path_type == PATH_TYPE_TOOL and tools_used:
        result[JSON_FIELD_TOOLS_USED] = tools_used
    
    return result
