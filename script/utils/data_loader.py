"""
数据加载模块
从文件加载增强路径信息和题目类型信息
"""
import json
import os
from typing import Any, Dict, Optional, Tuple

from utils.constants import (
    JSON_FIELD_KNOWLEDGE,
    JSON_FIELD_MESSAGES,
    JSON_FIELD_PATH_TYPE,
    JSON_FIELD_QUESTION,
    JSON_FIELD_TOOL,
    JSON_FIELD_TOOLS,
    NONMCQ_TYPE_NUMERIC,
    NONMCQ_TYPE_YESNO,
    PATH_TYPE_KNOWLEDGE,
    PATH_TYPE_TOOL,
    PATH_TYPE_UNKNOWN,
)
from utils.data_processor import extract_tools_from_messages


def load_enhancement_paths(
    dump_file: str
) -> Dict[str, Dict[str, Any]]:
    """
    从 thirdgen_dump.jsonl 加载每个问题的增强路径类型和工具信息
    
    Args:
        dump_file: thirdgen_dump.jsonl 文件路径
        
    Returns:
        问题到增强路径信息的映射，格式为：
        {question: {'path_type': str, 'tools': list}}
        path_type 为 'tool'、'knowledge' 或 'unknown'
        tools 为使用的工具名称列表（仅当 path_type 为 'tool' 时）
    """
    paths: Dict[str, Dict[str, Any]] = {}
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                data = json.loads(line.strip())
                question = data.get(JSON_FIELD_QUESTION, '').strip()
                if not question:
                    continue
                
                has_tool = (
                    JSON_FIELD_TOOL in data
                    and data[JSON_FIELD_TOOL] is not None
                )
                has_knowledge = (
                    JSON_FIELD_KNOWLEDGE in data
                    and data[JSON_FIELD_KNOWLEDGE] is not None
                )
                
                # 确定增强路径：tool 优先于 knowledge
                path_info = {}
                if has_tool:
                    tool_data = data.get(JSON_FIELD_TOOL, {})
                    messages = tool_data.get(JSON_FIELD_MESSAGES, [])
                    tools = extract_tools_from_messages(messages)
                    path_info = {
                        JSON_FIELD_PATH_TYPE: PATH_TYPE_TOOL,
                        JSON_FIELD_TOOLS: tools
                    }
                elif has_knowledge:
                    path_info = {
                        JSON_FIELD_PATH_TYPE: PATH_TYPE_KNOWLEDGE,
                        JSON_FIELD_TOOLS: []
                    }
                else:
                    path_info = {
                        JSON_FIELD_PATH_TYPE: PATH_TYPE_UNKNOWN,
                        JSON_FIELD_TOOLS: []
                    }
                
                # 直接使用 question 作为 key
                paths[question] = path_info
                    
            except json.JSONDecodeError:
                continue
    
    return paths


def load_test_is_mcq_mapping(
    test_file: str
) -> Tuple[Dict[int, bool], Dict[int, Optional[str]]]:
    """
    从 test.jsonl 文件加载行号到 is_mcq 和填空题类型的映射
    
    Args:
        test_file: test.jsonl 文件路径
        
    Returns:
        (行号到 is_mcq 的映射字典, 行号到填空题类型的映射字典)
        行号从1开始，对应文件中的行号
        填空题类型: 'yesno' (Yes/No类型), 'numeric' (数值类型),
        None (选择题或其他)
    """
    is_mcq_map: Dict[int, bool] = {}
    nonmcq_type_map: Dict[int, Optional[str]] = {}
    
    if not os.path.exists(test_file):
        return is_mcq_map, nonmcq_type_map
    
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line.strip())
                    is_mcq = data.get('is_mcq', False)
                    is_mcq_map[line_num] = bool(is_mcq)
                    
                    # 如果是填空题，判断类型
                    if not is_mcq:
                        instruction = data.get('instruction', '').lower()
                        if 'yes or no' in instruction:
                            nonmcq_type_map[line_num] = NONMCQ_TYPE_YESNO
                        elif 'numeric' in instruction:
                            nonmcq_type_map[line_num] = NONMCQ_TYPE_NUMERIC
                        else:
                            nonmcq_type_map[line_num] = None
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"警告: 加载 test.jsonl 文件失败: {e}")
    
    return is_mcq_map, nonmcq_type_map
