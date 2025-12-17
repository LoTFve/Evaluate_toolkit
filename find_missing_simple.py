"""
Find missing questions by comparing line numbers in result.jsonl with test.jsonl.
"""
import argparse
import json
import os
import sys
from typing import Any, Dict, List, Set, Tuple

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Constants
DEFAULT_TEST_FILE = 'Reason_Knowledge_Dataset/test.jsonl'
LINE_IN_DATASET_KEY = 'lineInDataset'
QUESTION_KEY = 'question'
ANSWER_KEY = 'answer'
IS_MCQ_KEY = 'is_mcq'
SOURCE_KEY = 'source'


def load_test_questions(test_file: str) -> Tuple[Set[int], Dict[int, Dict[str, Any]]]:
    """
    Load test questions from test.jsonl file.
    
    Args:
        test_file: Path to test.jsonl file
    
    Returns:
        Tuple of (set of line numbers, dict mapping line numbers to question info)
    
    Raises:
        FileNotFoundError: If test file does not exist
    """
    test_line_numbers: Set[int] = set()
    test_questions: Dict[int, Dict[str, Any]] = {}
    
    if not os.path.exists(test_file):
        raise FileNotFoundError(f'Test file "{test_file}" not found')
    
    with open(test_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            if line.strip():
                test_line_numbers.add(line_num)
                try:
                    data = json.loads(line.strip())
                    test_questions[line_num] = {
                        QUESTION_KEY: data.get(QUESTION_KEY, ''),
                        ANSWER_KEY: data.get(ANSWER_KEY, ''),
                        IS_MCQ_KEY: data.get(IS_MCQ_KEY, False),
                        SOURCE_KEY: data.get(SOURCE_KEY, '')
                    }
                except json.JSONDecodeError:
                    continue
    
    return test_line_numbers, test_questions


def get_result_line_numbers(result_file: str) -> Set[int]:
    """
    Extract line numbers from result.jsonl file.
    
    Args:
        result_file: Path to result.jsonl file
    
    Returns:
        Set of line numbers found in result.jsonl
    """
    result_line_numbers: Set[int] = set()
    
    if not os.path.exists(result_file):
        return result_line_numbers
    
    with open(result_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line.strip())
                    line_in_dataset = data.get(LINE_IN_DATASET_KEY, 0)
                    if line_in_dataset > 0:
                        result_line_numbers.add(line_in_dataset)
                except json.JSONDecodeError:
                    continue
    
    return result_line_numbers


def find_missing_questions(
    test_line_numbers: Set[int],
    result_line_numbers: Set[int]
) -> List[int]:
    """
    Find missing questions by set difference.
    
    Args:
        test_line_numbers: Set of line numbers from test.jsonl
        result_line_numbers: Set of line numbers from result.jsonl
    
    Returns:
        Sorted list of missing line numbers
    """
    missing = test_line_numbers - result_line_numbers
    return sorted(missing)


def get_missing_details(
    missing: List[int],
    test_questions: Dict[int, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Get detailed information about missing questions.
    
    Args:
        missing: List of missing line numbers
        test_questions: Dict mapping line numbers to question info
    
    Returns:
        List of dictionaries containing detailed question information
    """
    details = []
    for line_num in missing:
        if line_num in test_questions:
            q_info = test_questions[line_num]
            details.append({
                'line_number': line_num,
                'question': q_info[QUESTION_KEY],
                'answer': q_info[ANSWER_KEY],
                'is_mcq': q_info[IS_MCQ_KEY],
                'source': q_info[SOURCE_KEY]
            })
    return details


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Find missing questions by comparing line numbers in result.jsonl with test.jsonl'
    )
    parser.add_argument(
        '--test-file',
        type=str,
        default=DEFAULT_TEST_FILE,
        help=f'Path to test.jsonl file (default: {DEFAULT_TEST_FILE})'
    )
    parser.add_argument(
        'result_file',
        type=str,
        help='Path to result.jsonl file'
    )
    
    args = parser.parse_args()
    
    # Step 1: Load test questions
    try:
        test_line_numbers, test_questions = load_test_questions(args.test_file)
    except FileNotFoundError as e:
        sys.exit(f'Error: {e}')
    
    # Step 2: Process result file
    result_line_numbers = get_result_line_numbers(args.result_file)
    missing = find_missing_questions(test_line_numbers, result_line_numbers)
    
    # Step 3: Build output data
    output_data: Dict[str, Any] = {
        'statistics': {
            'test_file': args.test_file,
            'result_file': args.result_file,
            'test_total_count': len(test_line_numbers),
            'result_count': len(result_line_numbers),
            'missing_count': len(missing),
            'missing_line_numbers': missing
        },
        'missing_details': get_missing_details(missing, test_questions) if missing else []
    }
    
    # Step 4: Auto-generate output file name and save
    result_dir = os.path.dirname(os.path.abspath(args.result_file))
    result_basename = os.path.splitext(os.path.basename(args.result_file))[0]
    output_file = os.path.join(result_dir, f'{result_basename}_missing.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(output_file)


if __name__ == '__main__':
    main()
