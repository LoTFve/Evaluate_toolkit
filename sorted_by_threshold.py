"""
Filter records with duration greater than specified threshold.
"""
import argparse
import json
import os
from typing import Any, Dict, List

# Constants
DEFAULT_THRESHOLDS = [30.0, 60.0, 120.0, 180.0, 300.0]
DATA_KEY = '数据'
STATS_KEY = '统计信息'
DURATION_KEY = 'duration_seconds'


def _process_single_threshold(
    original_data: List[Dict[str, Any]],
    original_stats: Dict[str, Any],
    duration_threshold: float
) -> Dict[str, Any]:
    """
    Process a single threshold and return the result.
    
    Args:
        original_data: Original data list
        original_stats: Original statistics
        duration_threshold: Duration threshold in seconds
    
    Returns:
        Threshold result dictionary
    """
    original_count = len(original_data)
    
    # Filter records
    filtered_data = [
        record for record in original_data
        if record.get(DURATION_KEY, 0) > duration_threshold
    ]
    
    # Sort filtered data by duration_seconds (descending: high to low)
    filtered_data.sort(key=lambda x: x.get(DURATION_KEY, 0), reverse=True)
    
    # Calculate statistics
    filtered_count = len(filtered_data)
    if filtered_count > 0:
        filtered_total_time = sum(record[DURATION_KEY] for record in filtered_data)
        filtered_avg_time = filtered_total_time / filtered_count
    else:
        filtered_total_time = 0.0
        filtered_avg_time = 0.0
    
    # Build threshold result
    filter_ratio = (filtered_count / original_count * 100) if original_count > 0 else 0.0
    
    return {
        STATS_KEY: {
            '筛选条件': f'{DURATION_KEY} > {duration_threshold}秒（{duration_threshold/60:.1f}分钟）',
            '筛选前总数': original_count,
            '筛选后总数': filtered_count,
            '筛选前总时间(秒)': original_stats.get('总时间(秒)', 0),
            '筛选后总时间(秒)': round(filtered_total_time, 3),
            '筛选前平均时间(秒)': original_stats.get('平均时间(秒)', 0),
            '筛选后平均时间(秒)': round(filtered_avg_time, 3),
            '筛选比例': f'{filter_ratio:.2f}%'
        },
        DATA_KEY: filtered_data
    }


def sorted_by_threshold(
    input_file: str,
    output_file: str,
    thresholds: List[float] = None
) -> None:
    """
    Filter records with duration greater than specified thresholds.
    Results for all thresholds are stored in the same output file.
    
    Args:
        input_file: Input JSON file path (must contain '数据' and '统计信息' keys)
        output_file: Output JSON file path
        thresholds: List of duration thresholds in seconds (default: [30, 60, 90, 120])
    
    Raises:
        FileNotFoundError: If input file does not exist
        json.JSONDecodeError: If input file is not valid JSON
        ValueError: If input file format is incorrect
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    
    # Read input file
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data: Dict[str, Any] = json.load(f)
    except json.JSONDecodeError:
        # Try reading as JSONL format
        raise ValueError(
            f'Input file "{input_file}" is not a valid JSON file. '
            f'Expected a JSON file with "数据" and "统计信息" keys. '
            f'If you have a JSONL file, please use a different file format.'
        )
    
    # Validate file format
    if DATA_KEY not in data:
        raise ValueError(
            f'Input file "{input_file}" does not contain "{DATA_KEY}" key. '
            f'Expected a JSON file with "数据" and "统计信息" structure.'
        )
    
    original_data: List[Dict[str, Any]] = data.get(DATA_KEY, [])
    original_stats: Dict[str, Any] = data.get(STATS_KEY, {})
    original_count = len(original_data)
    
    # Calculate original statistics
    original_total_time = sum(record[DURATION_KEY] for record in original_data)
    original_avg_time = original_total_time / original_count if original_count > 0 else 0.0
    
    # Process all thresholds (from high to low)
    threshold_results: Dict[str, Any] = {}
    sorted_thresholds = sorted(thresholds, reverse=True)
    
    for threshold in sorted_thresholds:
        threshold_key = f'阈值{threshold}秒'
        threshold_result = _process_single_threshold(
            original_data, original_stats, threshold
        )
        threshold_results[threshold_key] = threshold_result
        
        # Print summary for each threshold
        stats = threshold_result[STATS_KEY]
        print(f'阈值 {threshold}秒: {stats["筛选后总数"]}/{stats["筛选前总数"]} '
              f'({stats["筛选比例"]})')
    
    # Build overview
    overview: List[Dict[str, Any]] = []
    for threshold in sorted_thresholds:
        threshold_key = f'阈值{threshold}秒'
        stats = threshold_results[threshold_key][STATS_KEY]
        overview.append({
            '阈值(秒)': threshold,
            '筛选条件': f'> {threshold}秒',
            '记录数': stats['筛选后总数'],
            '平均时间(秒)': round(stats['筛选后平均时间(秒)'], 3),
            '总时间(秒)': round(stats['筛选后总时间(秒)'], 3),
            '筛选比例': stats['筛选比例']
        })
    
    # Ensure overview is sorted by threshold (high to low)
    overview.sort(key=lambda x: x['阈值(秒)'], reverse=True)
    
    # Build final output with overview
    output_data: Dict[str, Any] = {
        '总览': {
            '原始数据': {
                '记录数': original_count,
                '平均时间(秒)': round(original_avg_time, 3),
                '总时间(秒)': round(original_total_time, 3)
            },
            '阈值统计': overview
        },
        **threshold_results
    }
    
    # Save output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    # Print final summary
    print('\n筛选完成！')
    print(f'  输入文件: {input_file}')
    print(f'  输出文件: {output_file}')
    print(f'  处理了 {len(thresholds)} 个阈值: {", ".join(f"{t}秒" for t in sorted_thresholds)}')


def _generate_output_path(input_file: str) -> str:
    """
    Generate output file path based on input file.
    All thresholds are stored in the same output file.
    
    Args:
        input_file: Input file path
    
    Returns:
        Output file path
    """
    input_dir = os.path.dirname(os.path.abspath(input_file))
    input_basename = os.path.splitext(os.path.basename(input_file))[0]
    return os.path.join(input_dir, f'{input_basename}_sorted_by_threshold.json')


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Filter records with duration greater than specified thresholds'
    )
    parser.add_argument(
        'input_file',
        type=str,
        help='Input JSON file path'
    )
    parser.add_argument(
        '--thresholds',
        type=float,
        nargs='+',
        default=None,
        help=f'Duration thresholds in seconds (default: {DEFAULT_THRESHOLDS})'
    )
    
    args = parser.parse_args()
    
    thresholds = args.thresholds if args.thresholds else DEFAULT_THRESHOLDS
    output_file = _generate_output_path(args.input_file)
    sorted_by_threshold(args.input_file, output_file, thresholds)


if __name__ == '__main__':
    main()
