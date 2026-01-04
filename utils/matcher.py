"""
匹配模块
在增强路径字典中查找匹配的问题
"""
from typing import Any, Dict, Optional


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
