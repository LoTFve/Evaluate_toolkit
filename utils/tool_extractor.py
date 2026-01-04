"""
工具提取模块
从消息列表中提取工具名称
"""
from typing import Any, Dict, List

from utils.constants import (
    JSON_FIELD_FUNCTION,
    JSON_FIELD_NAME,
    JSON_FIELD_ROLE,
    JSON_FIELD_TOOL_CALLS,
)


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
