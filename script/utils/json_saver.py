"""
JSON保存模块
构建详细统计信息并保存到JSON文件
"""
import json
import re
from typing import Any, Dict, List

from utils.constants import (
    FIELD_ACCURACY,
    FIELD_CORRECT,
    FIELD_CORRECT_LINE_NUMBERS,
    FIELD_INCORRECT_LINE_NUMBERS,
    FIELD_LINE_NUMBERS,
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


def compress_line_number_arrays(json_str: str) -> str:
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
    
    pattern = (
        r'("(?:line_numbers|correct_line_numbers|incorrect_line_numbers)"'
        r'\s*:\s*)\[([\s\S]*?)\]'
    )
    return re.sub(pattern, compress_array, json_str)


def build_statistics_detail(
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
        incorrect_line_numbers = sorted(
            stats[FIELD_INCORRECT_LINE_NUMBERS]
        )
        
        total = stats[FIELD_TOTAL]
        correct = stats[FIELD_CORRECT]
        incorrect = total - correct
        
        def build_accuracy_entry(
            stats_dict: Dict[str, Any],
            correct_key: str,
            total_key: str,
            accuracy_key: str
        ) -> Dict[str, Any]:
            """
            构建正确率统计条目
            
            Args:
                stats_dict: 统计字典
                correct_key: 正确数字段名
                total_key: 总数字段名
                accuracy_key: 正确率字段名
                
            Returns:
                包含正确数、总数、正确率和百分比格式的字典
            """
            correct = stats_dict[correct_key]
            total = stats_dict[total_key]
            accuracy = stats_dict.get(accuracy_key, 0.0)
            return {
                correct_key: correct,
                total_key: total,
                accuracy_key: accuracy,
                f'{accuracy_key}_percentage': (
                    f"{accuracy*100:.2f}%" if total > 0 else "0.00%"
                )
            }
        
        statistics_detail[path_type] = {
            FIELD_CORRECT: correct,
            FIELD_TOTAL: total,
            FIELD_ACCURACY: stats[FIELD_ACCURACY],
            'accuracy_percentage': (
                f"{stats[FIELD_ACCURACY]*100:.2f}%"
            ),
            'incorrect': incorrect,
            'incorrect_percentage': (
                f"{incorrect/total*100:.2f}%"
                if total > 0 else "0.00%"
            ),
            **build_accuracy_entry(
                stats,
                FIELD_MCQ_CORRECT,
                FIELD_MCQ_TOTAL,
                FIELD_MCQ_ACCURACY
            ),
            **build_accuracy_entry(
                stats,
                FIELD_NONMCQ_CORRECT,
                FIELD_NONMCQ_TOTAL,
                FIELD_NONMCQ_ACCURACY
            ),
            **build_accuracy_entry(
                stats,
                FIELD_YESNO_CORRECT,
                FIELD_YESNO_TOTAL,
                FIELD_YESNO_ACCURACY
            ),
            **build_accuracy_entry(
                stats,
                FIELD_NUMERIC_CORRECT,
                FIELD_NUMERIC_TOTAL,
                FIELD_NUMERIC_ACCURACY
            ),
            FIELD_LINE_NUMBERS: line_numbers,
            FIELD_CORRECT_LINE_NUMBERS: correct_line_numbers,
            FIELD_INCORRECT_LINE_NUMBERS: incorrect_line_numbers
        }
    
    return statistics_detail


def save_output_file(
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
    statistics_detail = build_statistics_detail(stats_by_path)
    overall_accuracy = (
        total_correct / total_count if total_count > 0 else 0.0
    )
    
    output_data = {
        'summary': {
            'total_count': total_count,
            'total_correct': total_correct,
            'total_incorrect': total_count - total_correct,
            'overall_accuracy': overall_accuracy,
            'overall_accuracy_percentage': (
                f"{overall_accuracy*100:.2f}%"
                if total_count > 0 else "0.00%"
            )
        },
        'statistics_by_path': statistics_detail,
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json_str = json.dumps(output_data, ensure_ascii=False, indent=2)
        json_str = compress_line_number_arrays(json_str)
        f.write(json_str)
    
    print(f"\n详细结果已保存到: {output_file}")
