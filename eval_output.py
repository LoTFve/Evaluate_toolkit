"""评估模型输出结果的模块。

该模块提供了多种评估函数，用于处理选择题（MCQ）和填空题的答案评估。
支持单选题、多选题、Yes/No题目和数值题目的评估。
"""

import argparse
import json
import os
import re
from typing import Any

from loguru import logger

# 常量定义
DEFAULT_ANSWER_LENGTH = 26  # 默认答案选项数量（A-Z）
ALPHABET_SIZE = 26  # 字母表大小
SHORT_TEXT_THRESHOLD = 50  # 短文本阈值
MAX_WORDS_IN_SHORT_ANSWER = 3  # 短答案最大词数
MAX_WORDS_IN_LAST_LINE = 10  # 最后一行最大词数
DEFAULT_REL_TOL = 1e-2  # 默认相对误差容差（1%）
ZERO_THRESHOLD = 1e-10  # 零值判断阈值
ZERO_ABS_ERROR_THRESHOLD = 1e-6  # 零值绝对误差阈值
SMALL_VALUE_THRESHOLD = 10  # 小数值阈值
SMALL_VALUE_ABS_ERROR = 0.01  # 小数值绝对误差阈值

# 题目类型常量
QUESTION_CLASS_YES_NO = 1  # Yes/No 题目类型
QUESTION_CLASS_NUMERIC = 2  # 数值题目类型
QUESTION_CLASS_UNKNOWN = 0  # 未知题目类型


def _fallback_parse_answer(completion: str) -> set[str] | None:
    """回退方法：从文本中查找最后一个大写字母作为答案。
    
    Args:
        completion: 模型输出的文本
        
    Returns:
        包含单个大写字母的集合，如果未找到则返回 None
    """
    for letter in reversed(completion):
        if letter.isupper():
            return {letter}
    return None


def parse_answers(
    text: str, length: int = DEFAULT_ANSWER_LENGTH, multiple_correct: bool = False
) -> set[str]:
    """从模型输出中提取选择题答案。
    
    生成的响应必须符合 'ANSWER: <answers>' 格式，否则无法提取模型认为的"正确答案"。
    可以灵活处理 "AB"、"A,B"、"A B" 等格式。
    
    如果答案不符合预期格式，模型任务失败，最终会被标记为不正确。
    
    Args:
        text: 模型输出的文本
        length: 答案选项数量（默认26，即A-Z）
        multiple_correct: 是否为多选题
        
    Returns:
        提取的答案集合（字母集合，如 {'A', 'B'}）
    """
    # First check whether the string strictly ends with the expected answer
    # In this case, we're looking for a single line which contains the expected
    # ANSWER: <answer> string with only whitespace or a period/full stop at the end.
    match = re.search(
        r"(?i)^ANSWER\s*:\s*([A-Za-z\d ,]+)\s*(?:$|\n|\.)",
        text,
        flags=re.MULTILINE,
    )

    # If we couldn't match the strict version, we can try the less strict
    # version for backward compatibility
    if match is None:
        match = re.search(
            r"(?i)ANSWER\s*:\s*([A-Za-z\d ,]+)(?:[^\w]|\n|$|\.)",
            text,
        )

    if match is None:
        match = re.search(
            r"<final>(.*?)</final>",
            text,
        )

    if match is None:
        fallback_answer = _fallback_parse_answer(text)
        if fallback_answer:
            return fallback_answer

    if match is None:
        return set()

    matched = match.group(1)

    # Strip trailing period / full stop
    matched = matched.strip()
    matched = matched.rstrip(".")

    allowed_options = set(answer_character(i) for i in range(length))

    if multiple_correct:
        # Match must contain only the allowed choices
        # (may be separated by commas, spaces, the word 'and', or nothing at all)

        matched = matched.replace(" and ", "")

        matched = matched.replace(" ", "")

        split_comma = set(matched.split(","))
        if split_comma.issubset(allowed_options):
            answers = split_comma
            return answers

        split_nothing = set(matched)
        if split_nothing.issubset(allowed_options):
            answers = split_nothing
            return answers

    else:
        # Match must contain a single letter in the allowed choices
        if matched in allowed_options:
            answers = {matched}
            return answers

    return set()


def answer_character(index: int) -> str:
    """将数组索引转换为字符。
    
    Args:
        index: 数组索引（0-based）
        
    Returns:
        对应的字符，例如：0 -> 'A', 1 -> 'B', 26 -> '1', 27 -> '2'
        
    Examples:
        >>> answer_character(0)
        'A'
        >>> answer_character(1)
        'B'
        >>> answer_character(26)
        '1'
    """
    if index < ALPHABET_SIZE:
        return chr(ord("A") + index)
    return str(index - ALPHABET_SIZE + 1)


def answer_index(char: str) -> int:
    """将字符转换为数组索引。
    
    Args:
        char: 字符（字母或数字）
        
    Returns:
        对应的数组索引，例如：'A' -> 0, 'B' -> 1, '1' -> 26
        
    Raises:
        ValueError: 如果字符不是字母或数字
        
    Examples:
        >>> answer_index('A')
        0
        >>> answer_index('B')
        1
        >>> answer_index('1')
        26
    """
    if char.isalpha():
        return ord(char.upper()) - ord("A")
    if char.isnumeric():
        return ALPHABET_SIZE - 1 + int(char)
    raise ValueError(
        f"Unexpected multiple choice answer: {char} (must be a letter or number)"
    )


def extract_text_answer(
    text: str, question_class: int = QUESTION_CLASS_UNKNOWN, expected_answer: str = ""
) -> str:
    """提取填空题的文本答案（非选择题）。
    
    Args:
        text: 模型输出的文本
        question_class: 题目类型（1=yes/no, 2=numeric, 0=未知）
        expected_answer: 期望答案（用于智能提取，当前未使用）
        
    Returns:
        提取的答案字符串，如果无法提取则返回空字符串
    """
    if not text:
        return ""
    
    text = text.strip()
    
    # 如果文本很短（比如直接就是答案，如 "true", "yes", "4", "-88"），直接返回
    # 判断标准：文本长度小于等于阈值且不包含换行符
    if len(text) <= SHORT_TEXT_THRESHOLD and '\n' not in text:
        # 检查是否是简单的答案格式（单个词或数字）
        words = text.split()
        if len(words) <= MAX_WORDS_IN_SHORT_ANSWER:
            return text
    
    # 尝试匹配 ANSWER: 后面的内容（不限制为选择题格式）
    match = re.search(
        r"(?i)^ANSWER\s*:\s*(.+?)\s*(?:$|\n|\.)",
        text,
        flags=re.MULTILINE,
    )
    
    if match is None:
        match = re.search(
            r"(?i)ANSWER\s*:\s*(.+?)(?:[^\w]|\n|$|\.)",
            text,
        )
    
    if match is None:
        match = re.search(
            r"<final>(.*?)</final>",
            text,
        )
    
    # 如果找到了 ANSWER: 格式，先提取出来，但要根据题目类型进行验证
    answer_from_match = None
    if match:
        answer_from_match = match.group(1).strip()
        # 去除末尾句号
        answer_from_match = answer_from_match.rstrip(".")
    
    # 根据题目类型进行智能提取
    if question_class == QUESTION_CLASS_YES_NO:
        # Yes/No 题目：优先使用 ANSWER: 中的内容，但需要验证是否为 yes/no
        if answer_from_match:
            # 检查 ANSWER: 中的内容是否包含 yes/no
            yes_no_pattern = r'\b(yes|no|true|false)\b'
            match_in_answer = re.search(yes_no_pattern, answer_from_match, re.IGNORECASE)
            if match_in_answer:
                matched = match_in_answer.group(1).lower()
                # 标准化：true -> yes, false -> no
                if matched == "true":
                    return "yes"
                if matched == "false":
                    return "no"
                return matched
            # 如果 ANSWER: 中有内容但没有 yes/no，返回 match 本身（不继续搜索）
            return answer_from_match
        
        # 如果没有 ANSWER: 格式，尝试在整个文本中匹配
        yes_no_pattern = r'\b(yes|no|true|false)\b'
        match = re.search(yes_no_pattern, text, re.IGNORECASE)
        if match:
            matched = match.group(1).lower()
            # 标准化：true -> yes, false -> no
            if matched == "true":
                return "yes"
            if matched == "false":
                return "no"
            return matched
        # 如果没找到匹配，返回空字符串（不继续 fallback）
        return ""
    
    elif question_class == QUESTION_CLASS_NUMERIC:
        # 数值题目：优先使用 ANSWER: 中的内容，但需要验证是否为数值
        if answer_from_match:
            # 检查 ANSWER: 中的内容是否包含数值
            num_match_in_answer = re.search(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', answer_from_match)
            if num_match_in_answer:
                return num_match_in_answer.group()
            # 如果 ANSWER: 中有内容但没有数值，返回 match 本身（不继续搜索）
            return answer_from_match
        
        # 如果没有 ANSWER: 格式，从最后50个字符中提取数值
        last_50_chars = text[-50:] if len(text) > 50 else text
        num_match = re.search(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', last_50_chars)
        if num_match:
            return num_match.group()
        # 如果没找到匹配，返回空字符串（不继续 fallback）
        return ""
    
    # 对于未知类型的题目，如果找到了 ANSWER: 格式，直接返回
    if answer_from_match:
        return answer_from_match
    
    # 如果都没有匹配到，返回空字符串
    return ""


def exact_match(prediction: str, reference: str) -> float:
    """Yes/No 题目的精确匹配评估（严格匹配，不处理变体）。
    
    Args:
        prediction: 预测答案
        reference: 标准答案
        
    Returns:
        1.0 如果匹配，否则 0.0
    """
    pred_clean = prediction.strip().lower()
    ref_clean = reference.strip().lower()
    return 1.0 if pred_clean == ref_clean else 0.0


def parse_digits(num: str | int | float) -> float | None:
    """解析数字字符串，支持逗号分隔符和百分比格式。
    
    Args:
        num: 数字字符串（可能包含逗号或百分比符号），也可以是数字类型
        
    Returns:
        解析后的浮点数，如果无法解析则返回 None
    """
    num_str = re.sub(',', '', str(num))
    try:
        return float(num_str)
    except (ValueError, TypeError):
        if num_str.endswith('%'):
            num_str = num_str[:-1]
            if num_str.endswith('\\'):
                num_str = num_str[:-1]
            try:
                return float(num_str) / 100
            except (ValueError, TypeError):
                pass
    return None


def is_digit(num: str | int | float) -> bool:
    """检查字符串是否可以解析为数字（与 parse_digits 配对使用）。
    
    Args:
        num: 待检查的字符串或数字
        
    Returns:
        如果可以解析为数字则返回 True，否则返回 False
    """
    return parse_digits(num) is not None


def internal_numeric_acc(
    prediction: str,
    reference: str,
    include_percentage: bool = True,
    rel_tol: float = DEFAULT_REL_TOL
) -> float:
    """
    数值题目的评估（考虑数值精度，支持百分比格式）
    
    Args:
        prediction: 预测答案（字符串）
        reference: 标准答案（字符串或数字）
        include_percentage: 是否考虑百分比格式（如 0.5, 50, 50% 都视为等价）
        rel_tol: 相对误差容差（默认 1%，即 0.01）
        
    Returns:
        1.0 如果数值匹配（在容差范围内），否则 0.0
    """
    if prediction is None or reference is None:
        return 0.0
    
    # 转换为字符串并去除空白
    pred_str = str(prediction).strip().lower() if prediction else ""
    ref_str = str(reference).strip().lower() if reference else ""
    
    # 先检查字符串是否完全匹配（不区分大小写）
    if pred_str == ref_str:
        return 1.0
    
    try:
        # 检查是否都是数字格式
        if is_digit(prediction) and is_digit(reference):
            pred_num = parse_digits(prediction)
            ref_num = parse_digits(reference)
            
            if pred_num is None or ref_num is None:
                return 0.0
            
            # 如果 include_percentage=True，考虑 reference 的多种形式
            if include_percentage:
                # 考虑 reference/100, reference, reference*100 三种形式
                gt_results = [ref_num / 100, ref_num, ref_num * 100]
            else:
                gt_results = [ref_num]
            
            # 对每种可能的参考值进行比较
            for item in gt_results:
                try:
                    abs_error = abs(pred_num - item)
                    
                    # 如果参考值为0，只使用绝对误差
                    if abs(item) < ZERO_THRESHOLD:
                        if abs_error < ZERO_ABS_ERROR_THRESHOLD:
                            return 1.0
                        continue
                    
                    # 计算相对误差
                    rel_error = abs_error / abs(item)
                    
                    # 使用相对误差容差进行比较
                    if rel_error < rel_tol:
                        return 1.0
                    
                    # 对于小数值，也考虑绝对误差
                    if abs(item) < SMALL_VALUE_THRESHOLD and abs_error < SMALL_VALUE_ABS_ERROR:
                        return 1.0
                        
                except (ZeroDivisionError, ValueError, TypeError):
                    continue
            
            return 0.0
    except (ValueError, TypeError):
        pass
    
    return 0.0


def determine_question_class(_record: dict[str, Any], expected_answer: str) -> int:
    """判断题目类型。
    
    严格根据 expected_answer 判断：
    - 如果 expected_answer 是 "Yes" 或 "No"（不区分大小写），返回 QUESTION_CLASS_YES_NO
    - 如果 expected_answer 可以转换为数值，返回 QUESTION_CLASS_NUMERIC
    - 其他情况返回 QUESTION_CLASS_UNKNOWN
    
    Args:
        _record: 记录字典（未使用，保留以保持接口一致，使用下划线前缀表示未使用）
        expected_answer: 期望答案
        
    Returns:
        题目类型：QUESTION_CLASS_YES_NO (1), QUESTION_CLASS_NUMERIC (2), 
        QUESTION_CLASS_UNKNOWN (0)
    """
    expected_str = str(expected_answer).strip()
    expected_lower = expected_str.lower()
    
    # 检查是否是 yes/no 类型（严格判断：只识别 "Yes" 或 "No"）
    if expected_lower in ("yes", "no"):
        return QUESTION_CLASS_YES_NO
    
    # 检查是否是数值类型
    try:
        float(expected_str)
        return QUESTION_CLASS_NUMERIC
    except (ValueError, TypeError):
        pass
    
    # 默认 fallback
    return QUESTION_CLASS_UNKNOWN


def _print_mismatch_info(
    line_num: str | int,
    expected: str,
    predicted: str | set[str],
    text_snippet: str,
    metric_name: str | None = None
) -> None:
    """打印答案不匹配的信息。
    
    Args:
        line_num: 行号
        expected: 期望答案
        predicted: 预测答案
        text_snippet: 答案文本片段（最后50字符）
        metric_name: 评估指标名称（可选）
    """
    if metric_name:
        print(f"[行 {line_num}] 答案不匹配 ({metric_name}):")
    else:
        print(f"[行 {line_num}] 答案不匹配:")
    print(f"  期望答案: {expected}")
    print(f"  预测答案: {predicted}")
    print(f"  答案文本 (最后50字符): {text_snippet}")
    print("")


def process_line(record: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """处理单行记录，返回正确率和详细信息。
    
    Args:
        record: 包含答案和期望答案的记录字典
        
    Returns:
        元组：(正确率, 详细信息字典)
    """
    if "answer" in record and "expectedAnswer" in record:
        text = record["answer"]
        target = record["expectedAnswer"]
    elif "sample_score" in record and "target" in record:
        text = record["sample_score"]["score"]["prediction"]
        target = record["target"]
    else:
        line_num = record.get("lineInDataset", "未知")
        logger.error(f"无法找到预测文本或目标答案字段 (lineInDataset: {line_num})")
        return 0.0, {
            "lineInDataset": line_num,
            "expectedAnswer": "",
            "prediction": set(),
            "accuracy": 0.0,
            "is_correct": False,
            "error": "无法找到预测文本或目标答案字段"
        }
    
    line_num = record.get("lineInDataset", "未知")
    
    dataset = record.get("dataset", "").lower()
    is_mcq = "nomcq" not in dataset and "mcq" in dataset
    
    if is_mcq:
        # MCQ 题目（包含单选和多选）
        if len(target) == 1:
            # 单选题
            prediction = parse_answers(text)
            is_correct = target in prediction
            accuracy = 1.0 if is_correct else 0.0
            
            detail = {
                "lineInDataset": line_num,
                "expectedAnswer": target,
                "prediction": list(prediction),
                "accuracy": accuracy,
                "is_correct": is_correct,
                "answer_text_last50": text[-50:] if len(text) > 50 else text
            }
            
            if not is_correct:
                _print_mismatch_info(
                    line_num, target, prediction, text[-50:] if len(text) > 50 else text
                )
            
            return accuracy, detail
        else:
            # 多选题
            prediction = parse_answers(text, DEFAULT_ANSWER_LENGTH, multiple_correct=True)
            den = len(
                parse_answers(f"ANSWER: {target}", DEFAULT_ANSWER_LENGTH, multiple_correct=True)
            )
            if den == 0:
                msg = f"Target contains no options. target: {target}. This answer will be viewed as incorrect. (lineInDataset: {line_num})"
                logger.warning(msg)
                return 0.0, {
                    "lineInDataset": line_num,
                    "expectedAnswer": target,
                    "prediction": list(prediction),
                    "accuracy": 0.0,
                    "is_correct": False,
                    "error": msg
                }
            num = 0
            for candidate in prediction:
                if candidate in target:
                    num += 1
            accuracy = num / den
            
            detail = {
                "lineInDataset": line_num,
                "expectedAnswer": target,
                "prediction": list(prediction),
                "accuracy": accuracy,
                "is_correct": accuracy == 1.0,
                "partial_correct": num,
                "total_expected": den,
                "answer_text_last50": text[-50:] if len(text) > 50 else text
            }
            
            return accuracy, detail
    else:
        # 填空题（非 MCQ）
        # 先判断题目类型，然后根据类型进行智能提取
        question_class = determine_question_class(record, target)
        prediction_text = extract_text_answer(text, question_class, target)
        
        if question_class == QUESTION_CLASS_YES_NO:
            # Yes/No 题目，使用 exact_match
            accuracy = exact_match(prediction_text, target)
            metric_name = "exact_match"
        elif question_class == QUESTION_CLASS_NUMERIC:
            # 数值题目，使用 internal_numeric_acc
            accuracy = internal_numeric_acc(prediction_text, target)
            metric_name = "internal_numeric_acc"
        else:
            # Fallback: 使用 exact_match
            accuracy = exact_match(prediction_text, target)
            metric_name = "exact_match (fallback)"
        
        is_correct = accuracy == 1.0
        
        detail = {
            "lineInDataset": line_num,
            "expectedAnswer": target,
            "prediction": prediction_text,
            "accuracy": accuracy,
            "is_correct": is_correct,
            "question_class": question_class,
            "metric_used": metric_name,
            "answer_text_last50": text[-50:] if len(text) > 50 else text
        }
        
        if not is_correct:
            _print_mismatch_info(
                line_num,
                target,
                prediction_text,
                text[-50:] if len(text) > 50 else text,
                metric_name
            )
        
        return accuracy, detail


def main() -> None:
    """主函数：处理评估文件并生成评估结果。
    
    从输入的 JSONL 文件中读取记录，评估每条记录的正确率，
    并生成包含统计信息和详细结果的 JSON 文件。
    """
    parser = argparse.ArgumentParser(description="评估模型输出结果")
    parser.add_argument("file_path", type=str, help="输入 JSONL 文件路径")
    args = parser.parse_args()

    file = args.file_path
    # 输出文件默认在输入文件同目录
    input_abs_path = os.path.abspath(file)
    input_dir = os.path.dirname(input_abs_path)
    input_basename = os.path.basename(input_abs_path)
    base_name = os.path.splitext(input_basename)[0]
    output_file = os.path.join(input_dir, f"{base_name}_eval_result.json")
    
    results: list[dict[str, Any]] = []
    total_count = 0
    correct_count = 0
    total_accuracy = 0.0
    
    try:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    total_count += 1
                    acc, detail = process_line(record)
                    results.append(detail)
                    total_accuracy += acc
                    if acc == 1.0:
                        correct_count += 1
                except json.JSONDecodeError as e:
                    logger.error(f"解析 JSON 行失败: {e}")
                    continue
    except FileNotFoundError:
        logger.error(f"文件未找到: {file}")
        return
    except IOError as e:
        logger.error(f"读取文件失败: {e}")
        return
    
    overall_accuracy = total_accuracy / total_count if total_count > 0 else 0.0
    
    # 构建输出数据
    output_data: dict[str, Any] = {
        "summary": {
            "total_count": total_count,
            "correct_count": correct_count,
            "incorrect_count": total_count - correct_count,
            "overall_accuracy": overall_accuracy,
            "overall_accuracy_percentage": f"{overall_accuracy * 100:.2f}%"
        },
        "results": results
    }
    
    # 保存到 JSON 文件
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存文件失败: {e}")
        return
    
    # 打印统计信息
    print(f"\n总题目数: {total_count}")
    print(f"正确数: {correct_count}")
    print(f"错误数: {total_count - correct_count}")
    print(f"总体正确率: {overall_accuracy:.4f} ({overall_accuracy * 100:.2f}%)")
    print(f"\n详细结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
