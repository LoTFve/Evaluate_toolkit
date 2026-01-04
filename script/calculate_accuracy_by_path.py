"""
根据 thirdgen_dump.jsonl 获取每个问题的增强路径类型
匹配 result.jsonl 中的答案
使用 eval_output.py 的逻辑计算每道题是否正确

主脚本：调用各个独立模块完成完整流程
"""
import argparse
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from utils.accuracy_calculator import (
    calculate_accuracy,
    calculate_path_accuracies,
)
from utils.constants import (
    JSON_FIELD_LINE_IN_DATASET,
    JSON_FIELD_PATH_TYPE,
    JSON_FIELD_QUESTION,
    JSON_FIELD_TOOLS,
    PATH_TYPE_UNKNOWN,
)
from utils.data_loader import (
    load_enhancement_paths,
    load_test_is_mcq_mapping,
)
from utils.excel_exporter import export_to_excel
from utils.formatter import print_statistics_table
from utils.json_saver import save_output_file
from utils.data_processor import (
    create_result_record,
    find_matching_question,
)
from utils.statistics_manager import (
    create_stats_dict,
    update_statistics,
)


def match_and_calculate(
    result_file: str,
    enhancement_paths: Dict[str, Dict[str, Any]],
    output_file: Optional[str] = None,
    test_file: Optional[str] = None,
    excel_file: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    匹配 result.jsonl 和增强路径，计算正确率
    
    Args:
        result_file: result.jsonl 文件路径
        enhancement_paths: 问题到增强路径信息的映射
        output_file: 输出 JSON 文件路径，如果为 None 则不保存
        test_file: test.jsonl 文件路径（用于获取 is_mcq 信息），
        如果为 None 则不区分选择题和填空题
        excel_file: Excel 文件路径，如果为 None 则不导出Excel
        
    Returns:
        (结果列表, 按路径类型的统计字典) 元组
    """
    results: List[Dict[str, Any]] = []
    stats_by_path = create_stats_dict()
    
    # 加载 test.jsonl 文件中的 is_mcq 和填空题类型映射
    # （通过行号匹配）
    is_mcq_map: Dict[int, bool] = {}
    nonmcq_type_map: Dict[int, Optional[str]] = {}
    if test_file and os.path.exists(test_file):
        is_mcq_map, nonmcq_type_map = load_test_is_mcq_mapping(
            test_file
        )
    
    with open(result_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                record = json.loads(line.strip())
                question = record.get(JSON_FIELD_QUESTION, '').strip()
                line_in_dataset = record.get(JSON_FIELD_LINE_IN_DATASET, 0)
                
                # 从 test.jsonl 中获取 is_mcq 和填空题类型信息
                # （通过行号匹配）
                is_mcq = (
                    is_mcq_map.get(line_in_dataset)
                    if is_mcq_map else None
                )
                nonmcq_type = (
                    nonmcq_type_map.get(line_in_dataset)
                    if nonmcq_type_map else None
                )
                
                # 匹配增强路径（使用子串匹配）
                path_info = find_matching_question(
                    question, enhancement_paths
                )
                if path_info is None:
                    path_info = {
                        JSON_FIELD_PATH_TYPE: PATH_TYPE_UNKNOWN,
                        JSON_FIELD_TOOLS: []
                    }
                path_type = path_info.get(
                    JSON_FIELD_PATH_TYPE, PATH_TYPE_UNKNOWN
                )
                tools_used = path_info.get(JSON_FIELD_TOOLS, [])
                
                # 计算正确率
                accuracy = calculate_accuracy(record, line_in_dataset)
                is_correct = accuracy == 1.0
                
                # 创建结果记录
                result = create_result_record(
                    record, path_type, accuracy, tools_used
                )
                results.append(result)
                
                # 更新统计（传入 is_mcq 和填空题类型信息）
                update_statistics(
                    stats_by_path,
                    path_type,
                    line_in_dataset,
                    is_correct,
                    is_mcq,
                    nonmcq_type
                )
                
            except json.JSONDecodeError as e:
                print(f"解析错误 (lineInDataset: {line_in_dataset}): {e}")
                continue
    
    # 计算各路径的正确率
    calculate_path_accuracies(stats_by_path)
    
    # 打印统计信息
    total_correct, total_count = print_statistics_table(stats_by_path)
    
    # 保存详细结果
    if output_file:
        save_output_file(
            output_file, results, stats_by_path,
            total_correct, total_count
        )
    
    # 导出Excel文件
    if excel_file:
        export_to_excel(stats_by_path, excel_file)
    
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
    result_basename = os.path.splitext(
        os.path.basename(result_abs_path)
    )[0]
    return os.path.join(
        result_dir, f"{result_basename}_accuracy_by_path.json"
    )


def main() -> None:
    """主函数：解析命令行参数并执行计算"""
    parser = argparse.ArgumentParser(
        description=(
            "根据 thirdgen_dump.jsonl 获取每个问题的增强路径类型，"
            "匹配 result.jsonl 中的答案，计算正确率"
        )
    )
    parser.add_argument(
        "--dump_file",
        type=str,
        default="ninth/ninth_thirdgen_dump.jsonl",
        help=(
            "thirdgen_dump.jsonl 文件路径"
            "（默认: ninth/ninth_thirdgen_dump.jsonl）"
        )
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
        help=(
            "test.jsonl 文件路径（用于获取 is_mcq 信息，"
            "默认: Reason_Knowledge_Dataset/test.jsonl）"
        )
    )
    parser.add_argument(
        "--excel",
        type=str,
        default=None,
        help=(
            "导出Excel文件路径（可选，如果指定则导出Excel表格，"
            "默认: 不导出）"
        )
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
        print(
            "正在加载 test.jsonl 文件（用于区分选择题和填空题类型）..."
        )
        is_mcq_map, nonmcq_type_map = load_test_is_mcq_mapping(
            args.test_file
        )
        print(f"已加载 {len(is_mcq_map)} 条记录的 is_mcq 信息")
        print(
            f"已加载 {len(nonmcq_type_map)} 条填空题的类型信息"
        )
    
    # 匹配并计算正确率
    print("\n正在匹配并计算正确率...")
    match_and_calculate(
        args.result_file,
        enhancement_paths,
        output_file,
        args.test_file,
        args.excel
    )


if __name__ == "__main__":
    main()
