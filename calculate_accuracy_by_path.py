"""
根据 thirdgen_dump.jsonl 获取每个问题的增强路径类型
匹配 result.jsonl 中的答案
使用 eval_output.py 的逻辑计算每道题是否正确
"""
import json
import os
import re
import argparse
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
from eval_output import process_line as eval_process_line

# 路径类型常量
PATH_TYPE_TOOL = 'tool'
PATH_TYPE_KNOWLEDGE = 'knowledge'
PATH_TYPE_UNKNOWN = 'unknown'

# 显示格式常量
SEPARATOR_WIDTH = 100
PATH_NAME_WIDTH = 20
NUMBER_WIDTH = 18
ANSWER_MAX_LENGTH = 50

# 统计字段名
FIELD_CORRECT = 'correct'
FIELD_TOTAL = 'total'
FIELD_ACCURACY = 'accuracy'
FIELD_LINE_NUMBERS = 'line_numbers'
FIELD_CORRECT_LINE_NUMBERS = 'correct_line_numbers'
FIELD_INCORRECT_LINE_NUMBERS = 'incorrect_line_numbers'

# 题目类型统计字段名
FIELD_MCQ_CORRECT = 'mcq_correct'
FIELD_MCQ_TOTAL = 'mcq_total'
FIELD_MCQ_ACCURACY = 'mcq_accuracy'
FIELD_NONMCQ_CORRECT = 'nonmcq_correct'
FIELD_NONMCQ_TOTAL = 'nonmcq_total'
FIELD_NONMCQ_ACCURACY = 'nonmcq_accuracy'
FIELD_YESNO_CORRECT = 'yesno_correct'
FIELD_YESNO_TOTAL = 'yesno_total'
FIELD_YESNO_ACCURACY = 'yesno_accuracy'
FIELD_NUMERIC_CORRECT = 'numeric_correct'
FIELD_NUMERIC_TOTAL = 'numeric_total'
FIELD_NUMERIC_ACCURACY = 'numeric_accuracy'

# 填空题类型常量
NONMCQ_TYPE_YESNO = 'yesno'
NONMCQ_TYPE_NUMERIC = 'numeric'

# JSON 字段名
JSON_FIELD_QUESTION = 'question'
JSON_FIELD_TOOL = 'tool'
JSON_FIELD_KNOWLEDGE = 'knowledge'
JSON_FIELD_MESSAGES = 'messages'
JSON_FIELD_ROLE = 'role'
JSON_FIELD_TOOL_CALLS = 'tool_calls'
JSON_FIELD_FUNCTION = 'function'
JSON_FIELD_NAME = 'name'
JSON_FIELD_LINE_IN_DATASET = 'lineInDataset'
JSON_FIELD_EXPECTED_ANSWER = 'expectedAnswer'
JSON_FIELD_ANSWER = 'answer'
JSON_FIELD_TOOLS_USED = 'tools_used'
JSON_FIELD_PATH_TYPE = 'path_type'
JSON_FIELD_TOOLS = 'tools'


def _create_default_stat_entry() -> Dict[str, Any]:
    """创建默认的统计条目"""
    return {
        FIELD_CORRECT: 0,
        FIELD_TOTAL: 0,
        FIELD_ACCURACY: 0.0,
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


def _extract_tools_from_messages(messages: List[Dict[str, Any]]) -> List[str]:
    """
    从消息列表中提取工具名称
    
    Args:
        messages: 消息列表
        
    Returns:
        工具名称列表
    """
    tools = []
    for msg in messages:
        if msg.get(JSON_FIELD_ROLE) == 'assistant' and JSON_FIELD_TOOL_CALLS in msg:
            for tool_call in msg.get(JSON_FIELD_TOOL_CALLS, []):
                func_name = tool_call.get(JSON_FIELD_FUNCTION, {}).get(JSON_FIELD_NAME, '')
                if func_name:
                    tools.append(func_name)
    return tools


def load_test_is_mcq_mapping(test_file: str) -> Tuple[Dict[int, bool], Dict[int, Optional[str]]]:
    """
    从 test.jsonl 文件加载行号到 is_mcq 和填空题类型的映射
    
    Args:
        test_file: test.jsonl 文件路径
        
    Returns:
        (行号到 is_mcq 的映射字典, 行号到填空题类型的映射字典)
        行号从1开始，对应文件中的行号
        填空题类型: 'yesno' (Yes/No类型), 'numeric' (数值类型), None (选择题或其他)
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


def _find_matching_question(question: str, enhancement_paths: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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


def load_enhancement_paths(dump_file: str) -> Dict[str, Dict[str, Any]]:
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
                
                has_tool = JSON_FIELD_TOOL in data and data[JSON_FIELD_TOOL] is not None
                has_knowledge = JSON_FIELD_KNOWLEDGE in data and data[JSON_FIELD_KNOWLEDGE] is not None
                
                # 确定增强路径：tool 优先于 knowledge
                path_info = {}
                if has_tool:
                    tool_data = data.get(JSON_FIELD_TOOL, {})
                    messages = tool_data.get(JSON_FIELD_MESSAGES, [])
                    tools = _extract_tools_from_messages(messages)
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


def _calculate_accuracy(record: Dict[str, Any], line_in_dataset: int) -> float:
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
        print(f"警告: 计算正确率时出错 (lineInDataset: {line_in_dataset}): {e}")
        return 0.0


def _truncate_answer(answer: str, max_length: int = ANSWER_MAX_LENGTH) -> str:
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


def _create_result_record(
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
        JSON_FIELD_LINE_IN_DATASET: record.get(JSON_FIELD_LINE_IN_DATASET, 0),
        'enhancement_path': path_type,
        FIELD_ACCURACY: accuracy,
        'is_correct': accuracy == 1.0,
        JSON_FIELD_EXPECTED_ANSWER: record.get(JSON_FIELD_EXPECTED_ANSWER, ''),
        JSON_FIELD_ANSWER: _truncate_answer(record.get(JSON_FIELD_ANSWER, ''))
    }
    
    if path_type == PATH_TYPE_TOOL and tools_used:
        result[JSON_FIELD_TOOLS_USED] = tools_used
    
    return result


def _update_statistics(
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
        nonmcq_type: 填空题类型（'yesno'=Yes/No类型，'numeric'=数值类型，None=未知或其他）
    """
    if path_type not in stats_by_path:
        stats_by_path[path_type] = _create_default_stat_entry()
    
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


def _calculate_accuracy_value(correct: int, total: int) -> float:
    """计算正确率"""
    return correct / total if total > 0 else 0.0


def _calculate_path_accuracies(stats_by_path: Dict[str, Dict[str, Any]]) -> None:
    """
    计算各路径的正确率
    
    Args:
        stats_by_path: 按路径类型的统计字典
    """
    for stats in stats_by_path.values():
        stats[FIELD_ACCURACY] = _calculate_accuracy_value(stats[FIELD_CORRECT], stats[FIELD_TOTAL])
        stats[FIELD_MCQ_ACCURACY] = _calculate_accuracy_value(stats[FIELD_MCQ_CORRECT], stats[FIELD_MCQ_TOTAL])
        stats[FIELD_NONMCQ_ACCURACY] = _calculate_accuracy_value(stats[FIELD_NONMCQ_CORRECT], stats[FIELD_NONMCQ_TOTAL])
        stats[FIELD_YESNO_ACCURACY] = _calculate_accuracy_value(stats[FIELD_YESNO_CORRECT], stats[FIELD_YESNO_TOTAL])
        stats[FIELD_NUMERIC_ACCURACY] = _calculate_accuracy_value(stats[FIELD_NUMERIC_CORRECT], stats[FIELD_NUMERIC_TOTAL])


def _format_stat_string(correct: int, total: int, accuracy: float) -> str:
    """格式化统计字符串：正确数/总数 (正确率%)"""
    if total > 0:
        return f"{correct}/{total} ({accuracy*100:.2f}%)"
    return "-"


def _print_statistics_table(stats_by_path: Dict[str, Dict[str, Any]]) -> Tuple[int, int]:
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
    print(f"{'增强路径':<{PATH_NAME_WIDTH}} {'选择题':<{NUMBER_WIDTH}} "
          f"{'Yes/No':<{NUMBER_WIDTH}} {'数值':<{NUMBER_WIDTH}} {'总计':<{NUMBER_WIDTH}}")
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
        mcq_str = _format_stat_string(
            stats[FIELD_MCQ_CORRECT], 
            stats[FIELD_MCQ_TOTAL], 
            stats.get(FIELD_MCQ_ACCURACY, 0.0)
        )
        yesno_str = _format_stat_string(
            stats[FIELD_YESNO_CORRECT], 
            stats[FIELD_YESNO_TOTAL], 
            stats.get(FIELD_YESNO_ACCURACY, 0.0)
        )
        numeric_str = _format_stat_string(
            stats[FIELD_NUMERIC_CORRECT], 
            stats[FIELD_NUMERIC_TOTAL], 
            stats.get(FIELD_NUMERIC_ACCURACY, 0.0)
        )
        total_str = _format_stat_string(
            stats[FIELD_CORRECT], 
            stats[FIELD_TOTAL], 
            stats[FIELD_ACCURACY]
        )
        
        print(f"{path_type:<{PATH_NAME_WIDTH}} {mcq_str:<{NUMBER_WIDTH}} "
              f"{yesno_str:<{NUMBER_WIDTH}} {numeric_str:<{NUMBER_WIDTH}} {total_str:<{NUMBER_WIDTH}}")
    
    # 打印总计行
    print("-" * SEPARATOR_WIDTH)
    if totals[FIELD_TOTAL] > 0:
        overall_accuracy = _calculate_accuracy_value(totals[FIELD_CORRECT], totals[FIELD_TOTAL])
        mcq_overall_accuracy = _calculate_accuracy_value(totals[FIELD_MCQ_CORRECT], totals[FIELD_MCQ_TOTAL])
        yesno_overall_accuracy = _calculate_accuracy_value(totals[FIELD_YESNO_CORRECT], totals[FIELD_YESNO_TOTAL])
        numeric_overall_accuracy = _calculate_accuracy_value(totals[FIELD_NUMERIC_CORRECT], totals[FIELD_NUMERIC_TOTAL])
        
        mcq_str = _format_stat_string(totals[FIELD_MCQ_CORRECT], totals[FIELD_MCQ_TOTAL], mcq_overall_accuracy)
        yesno_str = _format_stat_string(totals[FIELD_YESNO_CORRECT], totals[FIELD_YESNO_TOTAL], yesno_overall_accuracy)
        numeric_str = _format_stat_string(totals[FIELD_NUMERIC_CORRECT], totals[FIELD_NUMERIC_TOTAL], numeric_overall_accuracy)
        total_str = _format_stat_string(totals[FIELD_CORRECT], totals[FIELD_TOTAL], overall_accuracy)
        
        print(f"{'总计':<{PATH_NAME_WIDTH}} {mcq_str:<{NUMBER_WIDTH}} "
              f"{yesno_str:<{NUMBER_WIDTH}} {numeric_str:<{NUMBER_WIDTH}} {total_str:<{NUMBER_WIDTH}}")
    print("=" * SEPARATOR_WIDTH)
    
    return totals[FIELD_CORRECT], totals[FIELD_TOTAL]


def _compress_line_number_arrays(json_str: str) -> str:
    """
    将JSON字符串中的行号数组压缩为单行格式
    
    Args:
        json_str: JSON字符串
        
    Returns:
        压缩后的JSON字符串
    """
    def compress_array(match: re.Match) -> str:
        field_name = match.group(1)
        array_content = match.group(2)
        numbers = re.findall(r'\d+', array_content)
        compressed = ', '.join(numbers)
        return f'{field_name}[{compressed}]'
    
    pattern = r'("(?:line_numbers|correct_line_numbers|incorrect_line_numbers)"\s*:\s*)\[([\s\S]*?)\]'
    return re.sub(pattern, compress_array, json_str)


def _build_statistics_detail(
    stats_by_path: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    构建详细的统计信息
    
    Args:
        stats_by_path: 按路径类型的统计字典
        
    Returns:
        详细的统计信息字典
    """
    statistics_detail = {}
    
    for path_type in sorted(stats_by_path.keys()):
        stats = stats_by_path[path_type]
        line_numbers = sorted(stats[FIELD_LINE_NUMBERS])
        correct_line_numbers = sorted(stats[FIELD_CORRECT_LINE_NUMBERS])
        incorrect_line_numbers = sorted(stats[FIELD_INCORRECT_LINE_NUMBERS])
        
        total = stats[FIELD_TOTAL]
        correct = stats[FIELD_CORRECT]
        incorrect = total - correct
        
        def _build_accuracy_entry(stats_dict: Dict[str, Any], correct_key: str, total_key: str, accuracy_key: str) -> Dict[str, Any]:
            """构建正确率统计条目"""
            correct = stats_dict[correct_key]
            total = stats_dict[total_key]
            accuracy = stats_dict.get(accuracy_key, 0.0)
            return {
                correct_key: correct,
                total_key: total,
                accuracy_key: accuracy,
                f'{accuracy_key}_percentage': f"{accuracy*100:.2f}%" if total > 0 else "0.00%"
            }
        
        statistics_detail[path_type] = {
            FIELD_CORRECT: correct,
            FIELD_TOTAL: total,
            FIELD_ACCURACY: stats[FIELD_ACCURACY],
            'accuracy_percentage': f"{stats[FIELD_ACCURACY]*100:.2f}%",
            'incorrect': incorrect,
            'incorrect_percentage': f"{incorrect/total*100:.2f}%" if total > 0 else "0.00%",
            **_build_accuracy_entry(stats, FIELD_MCQ_CORRECT, FIELD_MCQ_TOTAL, FIELD_MCQ_ACCURACY),
            **_build_accuracy_entry(stats, FIELD_NONMCQ_CORRECT, FIELD_NONMCQ_TOTAL, FIELD_NONMCQ_ACCURACY),
            **_build_accuracy_entry(stats, FIELD_YESNO_CORRECT, FIELD_YESNO_TOTAL, FIELD_YESNO_ACCURACY),
            **_build_accuracy_entry(stats, FIELD_NUMERIC_CORRECT, FIELD_NUMERIC_TOTAL, FIELD_NUMERIC_ACCURACY),
            FIELD_LINE_NUMBERS: line_numbers,
            FIELD_CORRECT_LINE_NUMBERS: correct_line_numbers,
            FIELD_INCORRECT_LINE_NUMBERS: incorrect_line_numbers
        }
    
    return statistics_detail


def _save_output_file(
    output_file: str,
    results: List[Dict[str, Any]],
    stats_by_path: Dict[str, Dict[str, Any]],
    total_correct: int,
    total_count: int
) -> None:
    """
    保存输出文件
    
    Args:
        output_file: 输出文件路径
        results: 结果列表
        stats_by_path: 按路径类型的统计字典
        total_correct: 总正确数
        total_count: 总数量
    """
    statistics_detail = _build_statistics_detail(stats_by_path)
    overall_accuracy = total_correct / total_count if total_count > 0 else 0.0
    
    output_data = {
        'summary': {
            'total_count': total_count,
            'total_correct': total_correct,
            'total_incorrect': total_count - total_correct,
            'overall_accuracy': overall_accuracy,
            'overall_accuracy_percentage': f"{overall_accuracy*100:.2f}%" if total_count > 0 else "0.00%"
        },
        'statistics_by_path': statistics_detail,
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json_str = json.dumps(output_data, ensure_ascii=False, indent=2)
        json_str = _compress_line_number_arrays(json_str)
        f.write(json_str)
    
    print(f"\n详细结果已保存到: {output_file}")


def match_and_calculate(
    result_file: str,
    enhancement_paths: Dict[str, Dict[str, Any]],
    output_file: Optional[str] = None,
    test_file: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    匹配 result.jsonl 和增强路径，计算正确率
    
    Args:
        result_file: result.jsonl 文件路径
        enhancement_paths: 问题到增强路径信息的映射
        output_file: 输出 JSON 文件路径，如果为 None 则不保存
        test_file: test.jsonl 文件路径（用于获取 is_mcq 信息），如果为 None 则不区分选择题和填空题
        
    Returns:
        (结果列表, 按路径类型的统计字典) 元组
    """
    results: List[Dict[str, Any]] = []
    stats_by_path: Dict[str, Dict[str, Any]] = defaultdict(_create_default_stat_entry)
    
    # 加载 test.jsonl 文件中的 is_mcq 和填空题类型映射（通过行号匹配）
    is_mcq_map: Dict[int, bool] = {}
    nonmcq_type_map: Dict[int, Optional[str]] = {}
    if test_file and os.path.exists(test_file):
        is_mcq_map, nonmcq_type_map = load_test_is_mcq_mapping(test_file)
    
    with open(result_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                record = json.loads(line.strip())
                question = record.get(JSON_FIELD_QUESTION, '').strip()
                line_in_dataset = record.get(JSON_FIELD_LINE_IN_DATASET, 0)
                
                # 从 test.jsonl 中获取 is_mcq 和填空题类型信息（通过行号匹配）
                is_mcq = is_mcq_map.get(line_in_dataset) if is_mcq_map else None
                nonmcq_type = nonmcq_type_map.get(line_in_dataset) if nonmcq_type_map else None
                
                # 匹配增强路径（使用子串匹配）
                path_info = _find_matching_question(question, enhancement_paths)
                if path_info is None:
                    path_info = {JSON_FIELD_PATH_TYPE: PATH_TYPE_UNKNOWN, JSON_FIELD_TOOLS: []}
                path_type = path_info.get(JSON_FIELD_PATH_TYPE, PATH_TYPE_UNKNOWN)
                tools_used = path_info.get(JSON_FIELD_TOOLS, [])
                
                # 计算正确率
                accuracy = _calculate_accuracy(record, line_in_dataset)
                is_correct = accuracy == 1.0
                
                # 创建结果记录
                result = _create_result_record(record, path_type, accuracy, tools_used)
                results.append(result)
                
                # 更新统计（传入 is_mcq 和填空题类型信息）
                _update_statistics(stats_by_path, path_type, line_in_dataset, is_correct, is_mcq, nonmcq_type)
                
            except json.JSONDecodeError as e:
                print(f"解析错误 (lineInDataset: {line_in_dataset}): {e}")
                continue
    
    # 计算各路径的正确率
    _calculate_path_accuracies(stats_by_path)
    
    # 打印统计信息
    total_correct, total_count = _print_statistics_table(stats_by_path)
    
    # 保存详细结果
    if output_file:
        _save_output_file(output_file, results, stats_by_path, total_correct, total_count)
    
    return results, stats_by_path


def _generate_output_file_path(result_file: str) -> str:
    """
    根据结果文件路径生成输出文件路径（同目录）
    
    Args:
        result_file: 结果文件路径
        
    Returns:
        输出文件完整路径
    """
    result_abs_path = os.path.abspath(result_file)
    result_dir = os.path.dirname(result_abs_path)
    result_basename = os.path.splitext(os.path.basename(result_abs_path))[0]
    return os.path.join(result_dir, f"{result_basename}_accuracy_by_path.json")


def main() -> None:
    """主函数：解析命令行参数并执行计算"""
    parser = argparse.ArgumentParser(
        description="根据 thirdgen_dump.jsonl 获取每个问题的增强路径类型，匹配 result.jsonl 中的答案，计算正确率"
    )
    parser.add_argument(
        "--dump_file",
        type=str,
        default="ninth/ninth_thirdgen_dump.jsonl",
        help="thirdgen_dump.jsonl 文件路径（默认: ninth/ninth_thirdgen_dump.jsonl）"
    )
    parser.add_argument(
        "--result_file",
        type=str,
        default="ninth/ninth_result.jsonl",
        help="result.jsonl 文件路径（默认: ninth/ninth_result.jsonl）"
    )
    parser.add_argument(
        "--test_file",
        type=str,
        default="Reason_Knowledge_Dataset/test.jsonl",
        help="test.jsonl 文件路径（用于获取 is_mcq 信息，默认: Reason_Knowledge_Dataset/test.jsonl）"
    )
    args = parser.parse_args()
    
    # 生成输出文件路径
    output_file = _generate_output_file_path(args.result_file)
    
    # 加载增强路径信息
    print("正在加载增强路径信息...")
    enhancement_paths = load_enhancement_paths(args.dump_file)
    print(f"已加载 {len(enhancement_paths)} 个问题的增强路径")
    
    # 加载题目类型信息（如果文件存在）
    if args.test_file and os.path.exists(args.test_file):
        print(f"正在加载 test.jsonl 文件（用于区分选择题和填空题类型）...")
        is_mcq_map, nonmcq_type_map = load_test_is_mcq_mapping(args.test_file)
        print(f"已加载 {len(is_mcq_map)} 条记录的 is_mcq 信息")
        print(f"已加载 {len(nonmcq_type_map)} 条填空题的类型信息")
    
    # 匹配并计算正确率
    print("\n正在匹配并计算正确率...")
    match_and_calculate(args.result_file, enhancement_paths, output_file, args.test_file)


if __name__ == "__main__":
    main()
