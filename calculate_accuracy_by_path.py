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
SEPARATOR_WIDTH = 70
PATH_NAME_WIDTH = 20
NUMBER_WIDTH = 10
ANSWER_MAX_LENGTH = 50

# 统计字段名
FIELD_CORRECT = 'correct'
FIELD_TOTAL = 'total'
FIELD_ACCURACY = 'accuracy'
FIELD_LINE_NUMBERS = 'line_numbers'
FIELD_CORRECT_LINE_NUMBERS = 'correct_line_numbers'
FIELD_INCORRECT_LINE_NUMBERS = 'incorrect_line_numbers'

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
        FIELD_INCORRECT_LINE_NUMBERS: []
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
    is_correct: bool
) -> None:
    """
    更新统计信息
    
    Args:
        stats_by_path: 按路径类型的统计字典
        path_type: 增强路径类型
        line_in_dataset: 数据集中的行号
        is_correct: 是否正确
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


def _calculate_path_accuracies(stats_by_path: Dict[str, Dict[str, Any]]) -> None:
    """
    计算各路径的正确率
    
    Args:
        stats_by_path: 按路径类型的统计字典
    """
    for path_type in stats_by_path:
        stats = stats_by_path[path_type]
        if stats[FIELD_TOTAL] > 0:
            stats[FIELD_ACCURACY] = stats[FIELD_CORRECT] / stats[FIELD_TOTAL]


def _print_statistics_table(stats_by_path: Dict[str, Dict[str, Any]]) -> Tuple[int, int]:
    """
    打印统计信息表格
    
    Args:
        stats_by_path: 按路径类型的统计字典
        
    Returns:
        (总正确数, 总数量) 元组
    """
    print("=" * SEPARATOR_WIDTH)
    print("各增强路径的正确率统计")
    print("=" * SEPARATOR_WIDTH)
    print(f"{'增强路径':<{PATH_NAME_WIDTH}} {'正确数':<{NUMBER_WIDTH}} "
          f"{'总数':<{NUMBER_WIDTH}} {'正确率':<{NUMBER_WIDTH}}")
    print("-" * SEPARATOR_WIDTH)
    
    total_correct = 0
    total_count = 0
    
    for path_type in sorted(stats_by_path.keys()):
        stats = stats_by_path[path_type]
        total_correct += stats[FIELD_CORRECT]
        total_count += stats[FIELD_TOTAL]
        print(f"{path_type:<{PATH_NAME_WIDTH}} {stats[FIELD_CORRECT]:<{NUMBER_WIDTH}} "
              f"{stats[FIELD_TOTAL]:<{NUMBER_WIDTH}} {stats[FIELD_ACCURACY]*100:.2f}%")
    
    print("-" * SEPARATOR_WIDTH)
    if total_count > 0:
        overall_accuracy = total_correct / total_count
        print(f"{'总计':<{PATH_NAME_WIDTH}} {total_correct:<{NUMBER_WIDTH}} "
              f"{total_count:<{NUMBER_WIDTH}} {overall_accuracy*100:.2f}%")
    print("=" * SEPARATOR_WIDTH)
    
    return total_correct, total_count


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
        
        statistics_detail[path_type] = {
            FIELD_CORRECT: correct,
            FIELD_TOTAL: total,
            FIELD_ACCURACY: stats[FIELD_ACCURACY],
            'accuracy_percentage': f"{stats[FIELD_ACCURACY]*100:.2f}%",
            'incorrect': incorrect,
            'incorrect_percentage': f"{incorrect/total*100:.2f}%" if total > 0 else "0.00%",
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
    output_file: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    匹配 result.jsonl 和增强路径，计算正确率
    
    Args:
        result_file: result.jsonl 文件路径
        enhancement_paths: 问题到增强路径信息的映射
        output_file: 输出 JSON 文件路径，如果为 None 则不保存
        
    Returns:
        (结果列表, 按路径类型的统计字典) 元组
    """
    results: List[Dict[str, Any]] = []
    stats_by_path: Dict[str, Dict[str, Any]] = defaultdict(_create_default_stat_entry)
    
    with open(result_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                record = json.loads(line.strip())
                question = record.get(JSON_FIELD_QUESTION, '').strip()
                line_in_dataset = record.get(JSON_FIELD_LINE_IN_DATASET, 0)
                
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
                
                # 更新统计
                _update_statistics(stats_by_path, path_type, line_in_dataset, is_correct)
                
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
    args = parser.parse_args()
    
    dump_file = args.dump_file
    result_file = args.result_file
    
    # 生成输出文件路径
    output_file = _generate_output_file_path(result_file)
    
    print("正在加载增强路径信息...")
    enhancement_paths = load_enhancement_paths(dump_file)
    print(f"已加载 {len(enhancement_paths)} 个问题的增强路径")
    
    print("\n正在匹配并计算正确率...")
    results, stats = match_and_calculate(result_file, enhancement_paths, output_file)


if __name__ == "__main__":
    main()
