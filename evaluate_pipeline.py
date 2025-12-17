"""
Evaluation pipeline: Automatically run all evaluation scripts.
"""
import os
import sys
import subprocess
import argparse
from typing import Dict, List, Optional, Tuple


def _get_script_dir() -> str:
    """Get the directory where this script is located."""
    return os.path.dirname(os.path.abspath(__file__))


def _normalize_path(input_dir: str) -> str:
    """
    Normalize input directory path.
    
    Args:
        input_dir: Input directory path (absolute or relative)
    
    Returns:
        Normalized absolute path
    
    Raises:
        ValueError: If path does not exist or is not a directory
    """
    if os.path.isabs(input_dir):
        input_path = input_dir
    else:
        if os.path.exists(input_dir):
            input_path = os.path.abspath(input_dir)
        else:
            base_dir = _get_script_dir()
            input_path = os.path.join(base_dir, input_dir)
    
    input_path = os.path.normpath(os.path.abspath(input_path))
    
    if not os.path.exists(input_path):
        raise ValueError(f'Input directory does not exist: {input_path}')
    
    if not os.path.isdir(input_path):
        raise ValueError(f'Input path is not a directory: {input_path}')
    
    return input_path


def run_eval_output(result_file: str) -> bool:
    """
    Run eval_output.py to evaluate result file.
    
    Args:
        result_file: Path to result.jsonl file
    
    Returns:
        True if successful, False otherwise
    """
    print('\n' + '=' * 80)
    print('Step 1/4: Running eval_output.py')
    print('=' * 80)
    
    if not os.path.exists(result_file):
        print(f'Skipped: File does not exist {result_file}')
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, 'eval_output.py', result_file],
            cwd=_get_script_dir(),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f'Error: {e}')
        return False


def run_extract_enhancement_time(log_file: str) -> bool:
    """
    Run extract_enhancement_time.py to extract enhancement times.
    
    Args:
        log_file: Path to agent log file
    
    Returns:
        True if successful, False otherwise
    """
    print('\n' + '=' * 80)
    print('Step 2/4: Running extract_enhancement_time.py')
    print('=' * 80)
    
    if not os.path.exists(log_file):
        print(f'Skipped: File does not exist {log_file}')
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, 'extract_enhancement_time.py', log_file],
            cwd=_get_script_dir(),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f'Error: {e}')
        return False


def run_calculate_accuracy_by_path(dump_file: str, result_file: str) -> bool:
    """
    Run calculate_accuracy_by_path.py to calculate accuracy by path.
    
    Args:
        dump_file: Path to thirdgen_dump.jsonl file
        result_file: Path to result.jsonl file
    
    Returns:
        True if successful, False otherwise
    """
    print('\n' + '=' * 80)
    print('Step 3/4: Running calculate_accuracy_by_path.py')
    print('=' * 80)
    
    if not os.path.exists(dump_file):
        print(f'Skipped: File does not exist {dump_file}')
        return False
    if not os.path.exists(result_file):
        print(f'Skipped: File does not exist {result_file}')
        return False
    
    try:
        result = subprocess.run(
            [
                sys.executable,
                'calculate_accuracy_by_path.py',
                '--dump_file', dump_file,
                '--result_file', result_file
            ],
            cwd=_get_script_dir(),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f'Error: {e}')
        return False


def run_statistics_by_tool(accuracy_file: str) -> bool:
    """
    Run statistics_by_tool.py to generate tool statistics.
    
    Args:
        accuracy_file: Path to accuracy_by_path.json file
    
    Returns:
        True if successful, False otherwise
    """
    print('\n' + '=' * 80)
    print('Step 4/4: Running statistics_by_tool.py')
    print('=' * 80)
    
    if not os.path.exists(accuracy_file):
        print(f'Skipped: File does not exist {accuracy_file} '
              f'(need to run calculate_accuracy_by_path.py first)')
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, 'statistics_by_tool.py', accuracy_file],
            cwd=_get_script_dir(),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f'Error: {e}')
        return False


def run_find_missing(test_file: str, result_file: str) -> bool:
    """
    Run find_missing_simple.py to find missing questions.
    
    Args:
        test_file: Path to test.jsonl file
        result_file: Path to result.jsonl file
    
    Returns:
        True if successful, False otherwise
    """
    print('\n' + '=' * 80)
    print('Optional Step: Running find_missing_simple.py')
    print('=' * 80)
    
    if not os.path.exists(result_file):
        print(f'Skipped: File does not exist {result_file}')
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, 'find_missing_simple.py', '--test-file', test_file, result_file],
            cwd=_get_script_dir(),
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout:
            print(f'Output file: {result.stdout.strip()}')
        return result.returncode == 0
    except Exception as e:
        print(f'Error: {e}')
        return False


def run_sorted_by_threshold(enhancement_file: str) -> bool:
    """
    Run sorted_by_threshold.py to filter records by duration thresholds.
    
    Args:
        enhancement_file: Path to enhancement times JSON file
    
    Returns:
        True if successful, False otherwise
    """
    print('\n' + '=' * 80)
    print('Optional Step: Running sorted_by_threshold.py')
    print('=' * 80)
    
    if not os.path.exists(enhancement_file):
        print(f'Skipped: File does not exist {enhancement_file}')
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, 'sorted_by_threshold.py', enhancement_file],
            cwd=_get_script_dir(),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f'Error: {e}')
        return False


def evaluate_pipeline(
    input_dir: str,
    test_file: Optional[str] = None,
    run_missing_check: bool = False,
    run_threshold_filter: bool = False
) -> None:
    """
    Run the complete evaluation pipeline.
    
    Args:
        input_dir: Input directory path (absolute or relative)
        test_file: Path to test.jsonl file (for missing check)
        run_missing_check: Whether to run find_missing_simple.py
        run_threshold_filter: Whether to run sorted_by_threshold.py
    """
    try:
        input_path = _normalize_path(input_dir)
    except ValueError as e:
        print(f'Error: {e}')
        return
    
    dir_name = os.path.basename(input_path.rstrip(os.sep))
    
    # Build file paths
    result_file = os.path.join(input_path, f'{dir_name}_result.jsonl')
    log_file = os.path.join(input_path, f'{dir_name}_agent.log')
    dump_file = os.path.join(input_path, f'{dir_name}_thirdgen_dump.jsonl')
    accuracy_file = os.path.join(input_path, f'{dir_name}_accuracy_by_path.json')
    
    print('=' * 80)
    print(f'Starting evaluation pipeline: {input_dir}')
    print('=' * 80)
    print(f'Input directory: {input_path}')
    print(f'Result file: {result_file}')
    print(f'Log file: {log_file}')
    print(f'Dump file: {dump_file}')
    print('=' * 80)
    
    # Check required files
    required_files = {
        'Result file': result_file,
        'Log file': log_file,
        'Dump file': dump_file
    }
    
    print('\nChecking required files...')
    for name, path in required_files.items():
        if os.path.exists(path):
            print(f'  [OK] {name}: {path}')
        else:
            print(f'  [X] {name}: {path} (not found)')
    
    results: Dict[str, bool] = {}
    
    # Step 1: eval_output.py
    results['eval_output'] = run_eval_output(result_file)
    
    # Step 2: extract_enhancement_time.py
    results['extract_enhancement_time'] = run_extract_enhancement_time(log_file)
    
    # Step 3: calculate_accuracy_by_path.py
    results['calculate_accuracy_by_path'] = run_calculate_accuracy_by_path(
        dump_file, result_file
    )
    
    # Step 4: statistics_by_tool.py
    results['statistics_by_tool'] = run_statistics_by_tool(accuracy_file)
    
    # Optional: find_missing_simple.py
    if run_missing_check:
        if test_file:
            results['find_missing'] = run_find_missing(test_file, result_file)
        else:
            default_test_file = os.path.join(_get_script_dir(), 'Reason_Knowledge_Dataset', 'test.jsonl')
            results['find_missing'] = run_find_missing(default_test_file, result_file)
    
    # Optional: sorted_by_threshold.py
    if run_threshold_filter:
        enhancement_file = os.path.join(
            input_path, f'{dir_name}_agent_enhancement_times_method2.json'
        )
        results['sorted_by_threshold'] = run_sorted_by_threshold(enhancement_file)
    
    # Print summary
    print('\n' + '=' * 80)
    print('Evaluation Pipeline Summary')
    print('=' * 80)
    for step, success in results.items():
        status = '[OK] Success' if success else '[X] Failed/Skipped'
        print(f'  {step}: {status}')
    print('=' * 80)
    
    # Output file locations
    print(f'\nOutput directory: {input_path}')
    print('\nGenerated files:')
    output_files = [
        f'{dir_name}_result_eval_result.json',
        f'{dir_name}_agent_enhancement_statistics.json',
        f'{dir_name}_accuracy_by_path.json',
        f'{dir_name}_accuracy_by_path_statistics_by_tool.json',
        f'{dir_name}_accuracy_by_path_knowledge_questions.json'
    ]
    
    if run_missing_check:
        output_files.append(f'{dir_name}_result_missing.json')
    
    if run_threshold_filter:
        output_files.append(f'{dir_name}_agent_enhancement_times_method2_sorted_by_threshold.json')
    
    for filename in output_files:
        filepath = os.path.join(input_path, filename)
        if os.path.exists(filepath):
            print(f'  [OK] {filename}')
        else:
            print(f'  - {filename} (not generated)')


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Evaluation pipeline: Automatically run all evaluation scripts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use relative path (relative to current working directory or script directory)
  python evaluate_pipeline.py ninth
  python evaluate_pipeline.py ./ninth
  
  # Use absolute path
  python evaluate_pipeline.py C:\\Users\\honor\\Desktop\\thrid_model_analyse\\ninth
  
  # Run with optional steps
  python evaluate_pipeline.py ninth --missing-check --threshold-filter
  
  # Use current directory
  cd ninth
  python ../evaluate_pipeline.py .
        """
    )
    parser.add_argument(
        'input_dir',
        type=str,
        help='Input directory path (absolute or relative, e.g., ninth or C:\\path\\to\\ninth)'
    )
    parser.add_argument(
        '--test-file',
        type=str,
        default=None,
        help='Path to test.jsonl file (for missing check, default: Reason_Knowledge_Dataset/test.jsonl)'
    )
    parser.add_argument(
        '--missing-check',
        action='store_true',
        help='Run find_missing_simple.py to find missing questions'
    )
    parser.add_argument(
        '--threshold-filter',
        action='store_true',
        help='Run sorted_by_threshold.py to filter records by duration thresholds'
    )
    
    args = parser.parse_args()
    
    evaluate_pipeline(
        args.input_dir,
        test_file=args.test_file,
        run_missing_check=args.missing_check,
        run_threshold_filter=args.threshold_filter
    )


if __name__ == '__main__':
    main()
