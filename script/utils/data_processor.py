"""
数据处理工具模块
包含数据匹配、工具提取和结果构建功能
"""
from typing import Any, Dict, List, Optional

from utils.constants import (
    ANSWER_MAX_LENGTH,
    FIELD_ACCURACY,
    JSON_FIELD_ANSWER,
    JSON_FIELD_EXPECTED_ANSWER,
    JSON_FIELD_FUNCTION,
    JSON_FIELD_LINE_IN_DATASET,
    JSON_FIELD_NAME,
    JSON_FIELD_ROLE,
    JSON_FIELD_TOOL_CALLS,
    JSON_FIELD_TOOLS_USED,
    PATH_TYPE_TOOL,
)


# ==================== 数据匹配 ====================


def find_matching_question(
    question: str,
    enhancement_paths: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    在 enhancement_paths 中查找匹配的 question（使用子串匹配）
    
    Args:
        question: 要匹配的 question 字符串
        enhancement_paths: 增强路径映射字典
        
    Returns:
        匹配的路径信息，如果未找到则返回 None
    """
    question = question.strip()
    if not question:
        return None
    
    # 先尝试精确匹配
    if question in enhancement_paths:
        return enhancement_paths[question]
    
    # 尝试子串匹配：A in B 或 B in A
    for key, path_info in enhancement_paths.items():
        if question in key or key in question:
            return path_info
    
    return None


# ==================== 工具提取 ====================


def extract_tools_from_messages(
    messages: List[Dict[str, Any]]
) -> List[str]:
    """
    从消息列表中提取工具名称
    
    Args:
        messages: 消息列表
        
    Returns:
        工具名称列表
    """
    tools = []
    for msg in messages:
        if (
            msg.get(JSON_FIELD_ROLE) == 'assistant'
            and JSON_FIELD_TOOL_CALLS in msg
        ):
            for tool_call in msg.get(JSON_FIELD_TOOL_CALLS, []):
                func_name = (
                    tool_call.get(JSON_FIELD_FUNCTION, {})
                    .get(JSON_FIELD_NAME, '')
                )
                if func_name:
                    tools.append(func_name)
    return tools


# ==================== 结果构建 ====================


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
