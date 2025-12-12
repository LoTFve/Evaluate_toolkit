"""
统计各个工具做了多少题，做对多少题
"""
import json
import os
import re
import argparse
from collections import defaultdict
from typing import Dict, List, Any, Optional

# 常量定义
ENHANCEMENT_PATH_TOOL = 'tool'
ENHANCEMENT_PATH_KNOWLEDGE = 'knowledge'
LINE_NUMBER_FIELDS = ['line_numbers', 'correct_line_numbers', 'incorrect_line_numbers']

# 显示格式常量
SEPARATOR_WIDTH = 80
TOOL_NAME_WIDTH = 30
NUMBER_WIDTH = 10


def _create_default_tool_stats() -> Dict[str, Any]:
    """创建默认的工具统计字典"""
    return {
        'total': 0,
        'correct': 0,
        'incorrect': 0,
        'accuracy': 0.0,
        'line_numbers': [],
        'correct_line_numbers': [],
        'incorrect_line_numbers': []
    }


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


def _calculate_summary_stats(tool_stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算工具统计的汇总信息
    
    Args:
        tool_stats: 工具统计信息
        
    Returns:
        汇总统计信息
    """
    total_questions = sum(stats['total'] for stats in tool_stats.values())
    total_correct = sum(stats['correct'] for stats in tool_stats.values())
    total_incorrect = sum(stats['incorrect'] for stats in tool_stats.values())
    overall_accuracy = total_correct / total_questions if total_questions > 0 else 0.0
    
    return {
        'total_tools': len(tool_stats),
        'total_questions': total_questions,
        'total_correct': total_correct,
        'total_incorrect': total_incorrect,
        'overall_accuracy': overall_accuracy
    }


def statistics_by_tool(json_file: str) -> Dict[str, Dict[str, Any]]:
    """
    统计各个工具的使用情况和正确率
    
    Args:
        json_file: accuracy_by_path.json 文件路径
        
    Returns:
        工具统计信息字典，键为工具名称，值为统计信息
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    tool_stats: Dict[str, Dict[str, Any]] = defaultdict(_create_default_tool_stats)
    
    for result in results:
        if result.get('enhancement_path') != ENHANCEMENT_PATH_TOOL:
            continue
        
        tools_used = result.get('tools_used', [])
        if not tools_used:
            continue
        
        is_correct = result.get('is_correct', False)
        line_in_dataset = result.get('lineInDataset', 0)
        
        # 统计每个工具（可能有多个相同工具，使用集合去重）
        unique_tools = set(tools_used)
        for tool in unique_tools:
            stats = tool_stats[tool]
            stats['total'] += 1
            stats['line_numbers'].append(line_in_dataset)
            
            if is_correct:
                stats['correct'] += 1
                stats['correct_line_numbers'].append(line_in_dataset)
            else:
                stats['incorrect'] += 1
                stats['incorrect_line_numbers'].append(line_in_dataset)
    
    # 计算正确率并排序行号列表
    for tool, stats in tool_stats.items():
        if stats['total'] > 0:
            stats['accuracy'] = stats['correct'] / stats['total']
            stats['line_numbers'] = sorted(stats['line_numbers'])
            stats['correct_line_numbers'] = sorted(stats['correct_line_numbers'])
            stats['incorrect_line_numbers'] = sorted(stats['incorrect_line_numbers'])
    
    return dict(tool_stats)


def print_statistics(tool_stats: Dict[str, Dict[str, Any]]) -> None:
    """
    打印工具统计信息到控制台
    
    Args:
        tool_stats: 工具统计信息字典
    """
    print("=" * SEPARATOR_WIDTH)
    print("各工具使用情况统计")
    print("=" * SEPARATOR_WIDTH)
    print(f"{'工具名称':<{TOOL_NAME_WIDTH}} {'总数':<{NUMBER_WIDTH}} "
          f"{'正确':<{NUMBER_WIDTH}} {'错误':<{NUMBER_WIDTH}} {'正确率':<{NUMBER_WIDTH}}")
    print("-" * SEPARATOR_WIDTH)
    
    # 按总数降序排序
    sorted_tools = sorted(tool_stats.items(), key=lambda x: x[1]['total'], reverse=True)
    
    total_all = 0
    correct_all = 0
    
    for tool, stats in sorted_tools:
        total = stats['total']
        correct = stats['correct']
        incorrect = stats['incorrect']
        accuracy = stats['accuracy']
        
        total_all += total
        correct_all += correct
        
        print(f"{tool:<{TOOL_NAME_WIDTH}} {total:<{NUMBER_WIDTH}} "
              f"{correct:<{NUMBER_WIDTH}} {incorrect:<{NUMBER_WIDTH}} {accuracy*100:.2f}%")
    
    print("-" * SEPARATOR_WIDTH)
    overall_accuracy = correct_all / total_all if total_all > 0 else 0.0
    incorrect_all = total_all - correct_all
    print(f"{'总计':<{TOOL_NAME_WIDTH}} {total_all:<{NUMBER_WIDTH}} "
          f"{correct_all:<{NUMBER_WIDTH}} {incorrect_all:<{NUMBER_WIDTH}} {overall_accuracy*100:.2f}%")
    print("=" * SEPARATOR_WIDTH)


def save_statistics_to_json(
    tool_stats: Dict[str, Dict[str, Any]], 
    output_file: str, 
    input_file: Optional[str] = None
) -> None:
    """
    保存工具统计信息到JSON文件
    
    Args:
        tool_stats: 工具统计信息字典
        output_file: 输出文件路径
        input_file: 输入文件路径（已废弃，保留以兼容旧代码）
    """
    summary = _calculate_summary_stats(tool_stats)
    
    # 构建输出数据
    output_data = {
        'summary': summary,
        'statistics_by_tool': {}
    }
    
    # 按总数降序排序
    sorted_tools = sorted(tool_stats.items(), key=lambda x: x[1]['total'], reverse=True)
    
    for tool, stats in sorted_tools:
        output_data['statistics_by_tool'][tool] = {
            'total': stats['total'],
            'correct': stats['correct'],
            'incorrect': stats['incorrect'],
            'accuracy': stats['accuracy'],
            'accuracy_percentage': f"{stats['accuracy']*100:.2f}%",
            'incorrect_percentage': f"{stats['incorrect']/stats['total']*100:.2f}%" if stats['total'] > 0 else "0.00%",
            'line_numbers': stats['line_numbers'],
            'correct_line_numbers': stats['correct_line_numbers'],
            'incorrect_line_numbers': stats['incorrect_line_numbers']
        }
    
    # 写入文件并压缩行号数组
    with open(output_file, 'w', encoding='utf-8') as f:
        json_str = json.dumps(output_data, ensure_ascii=False, indent=2)
        json_str = _compress_line_number_arrays(json_str)
        f.write(json_str)
    
    print(f"\n详细统计已保存到: {output_file}")


def statistics_knowledge_questions(json_file: str) -> Dict[str, Any]:
    """
    统计知识增强使用的题目
    
    Args:
        json_file: accuracy_by_path.json 文件路径
        
    Returns:
        知识增强题目统计信息字典，包含总数、正确数、错误数、正确率、行号列表和详细信息
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    
    # 提取知识增强的题目
    knowledge_results = [
        r for r in results 
        if r.get('enhancement_path') == ENHANCEMENT_PATH_KNOWLEDGE
    ]
    
    # 按行号排序
    knowledge_results.sort(key=lambda x: x.get('lineInDataset', 0))
    
    # 提取所有行号
    line_numbers = [r.get('lineInDataset') for r in knowledge_results]
    correct_line_numbers = [
        r.get('lineInDataset') for r in knowledge_results 
        if r.get('is_correct')
    ]
    incorrect_line_numbers = [
        r.get('lineInDataset') for r in knowledge_results 
        if not r.get('is_correct')
    ]
    
    total = len(knowledge_results)
    correct = len(correct_line_numbers)
    incorrect = len(incorrect_line_numbers)
    accuracy = correct / total if total > 0 else 0.0
    
    return {
        'total': total,
        'correct': correct,
        'incorrect': incorrect,
        'accuracy': accuracy,
        'line_numbers': sorted(line_numbers),
        'correct_line_numbers': sorted(correct_line_numbers),
        'incorrect_line_numbers': sorted(incorrect_line_numbers),
        'details': knowledge_results
    }


def print_knowledge_statistics(knowledge_stats: Dict[str, Any]) -> None:
    """
    打印知识增强统计信息到控制台
    
    Args:
        knowledge_stats: 知识增强统计信息字典
    """
    print("=" * SEPARATOR_WIDTH)
    print("知识增强题目统计")
    print("=" * SEPARATOR_WIDTH)
    print(f"总题目数: {knowledge_stats['total']}")
    print(f"正确数: {knowledge_stats['correct']}")
    print(f"错误数: {knowledge_stats['incorrect']}")
    print(f"正确率: {knowledge_stats['accuracy']*100:.2f}%")
    print("=" * SEPARATOR_WIDTH)
    print(f"\n所有题目行号 ({knowledge_stats['total']} 题):")
    print(knowledge_stats['line_numbers'])
    print(f"\n正确题目行号 ({knowledge_stats['correct']} 题):")
    print(knowledge_stats['correct_line_numbers'])
    print(f"\n错误题目行号 ({knowledge_stats['incorrect']} 题):")
    print(knowledge_stats['incorrect_line_numbers'])


def save_knowledge_statistics_to_json(
    knowledge_stats: Dict[str, Any], 
    output_file: str, 
    input_file: Optional[str] = None
) -> None:
    """
    保存知识增强统计信息到JSON文件
    
    Args:
        knowledge_stats: 知识增强统计信息字典
        output_file: 输出文件路径
        input_file: 输入文件路径（已废弃，保留以兼容旧代码）
    """
    output_data = {
        'summary': {
            'total': knowledge_stats['total'],
            'correct': knowledge_stats['correct'],
            'incorrect': knowledge_stats['incorrect'],
            'accuracy': knowledge_stats['accuracy'],
            'accuracy_percentage': f"{knowledge_stats['accuracy']*100:.2f}%"
        },
        'line_numbers': knowledge_stats['line_numbers'],
        'correct_line_numbers': knowledge_stats['correct_line_numbers'],
        'incorrect_line_numbers': knowledge_stats['incorrect_line_numbers'],
        'details': knowledge_stats['details']
    }
    
    # 写入文件并压缩行号数组
    with open(output_file, 'w', encoding='utf-8') as f:
        json_str = json.dumps(output_data, ensure_ascii=False, indent=2)
        json_str = _compress_line_number_arrays(json_str)
        f.write(json_str)
    
    print(f"\n详细数据已保存到: {output_file}")


def _generate_output_file_path(input_file: str, suffix: str) -> str:
    """
    根据输入文件路径生成输出文件路径（同目录）
    
    Args:
        input_file: 输入文件路径
        suffix: 输出文件后缀（如 "_statistics_by_tool.json"）
        
    Returns:
        输出文件完整路径
    """
    input_abs_path = os.path.abspath(input_file)
    input_dir = os.path.dirname(input_abs_path)
    input_basename = os.path.basename(input_abs_path)
    base_name = os.path.splitext(input_basename)[0]
    return os.path.join(input_dir, f"{base_name}{suffix}")


def main() -> None:
    """主函数：解析命令行参数并执行统计"""
    parser = argparse.ArgumentParser(description="按工具统计准确率数据")
    parser.add_argument(
        "input_file",
        type=str,
        nargs='?',
        default="ninth/ninth_accuracy_by_path.json",
        help="输入的 accuracy_by_path.json 文件路径（默认: ninth/ninth_accuracy_by_path.json）"
    )
    args = parser.parse_args()
    
    input_file = args.input_file
    
    # 生成输出文件路径
    tool_output_file = _generate_output_file_path(input_file, "_statistics_by_tool.json")
    knowledge_output_file = _generate_output_file_path(input_file, "_knowledge_questions.json")
    
    print("正在读取数据...")
    
    # 统计工具使用情况
    tool_stats = statistics_by_tool(input_file)
    print(f"\n共找到 {len(tool_stats)} 个不同的工具\n")
    print_statistics(tool_stats)
    save_statistics_to_json(tool_stats, tool_output_file, input_file)
    
    # 统计知识增强题目
    print("\n" + "=" * SEPARATOR_WIDTH)
    knowledge_stats = statistics_knowledge_questions(input_file)
    print_knowledge_statistics(knowledge_stats)
    save_knowledge_statistics_to_json(knowledge_stats, knowledge_output_file, input_file)


if __name__ == "__main__":
    main()
