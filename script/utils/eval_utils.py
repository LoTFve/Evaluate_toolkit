"""
评估工具模块
提供评估相关的辅助函数和核心处理逻辑
"""
from typing import Any

from loguru import logger

from utils.answer_utils import (
    DEFAULT_ANSWER_LENGTH,
    determine_question_class,
    exact_match,
    extract_text_answer,
    internal_numeric_acc,
    parse_answers,
    QUESTION_CLASS_NUMERIC,
    QUESTION_CLASS_UNKNOWN,
    QUESTION_CLASS_YES_NO,
)


def _print_mismatch_info(
    line_num: str | int,
    expected: str,
    predicted: str | set[str],
    text_snippet: str,
    metric_name: str | None = None,
    verbose: bool = False
) -> None:
    """
    打印答案不匹配的信息
    
    Args:
        line_num: 行号
        expected: 期望答案
        predicted: 预测答案
        text_snippet: 答案文本片段（最后50字符）
        metric_name: 评估指标名称（可选）
        verbose: 是否输出打印信息（默认 False）
    """
    if not verbose:
        return
    
    if metric_name:
        print(f"[行 {line_num}] 答案不匹配 ({metric_name}):")
    else:
        print(f"[行 {line_num}] 答案不匹配:")
    print(f"  期望答案: {expected}")
    print(f"  预测答案: {predicted}")
    print(f"  答案文本 (最后50字符): {text_snippet}")
    print("")


def process_line(
    record: dict[str, Any],
    verbose: bool = False
) -> tuple[float, dict[str, Any]]:
    """
    处理单行记录，返回正确率和详细信息
    
    Args:
        record: 包含答案和期望答案的记录字典
        verbose: 是否输出打印信息（默认 False）
        
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
        logger.error(
            f"无法找到预测文本或目标答案字段 "
            f"(lineInDataset: {line_num})"
        )
        return 0.0, {
            "lineInDataset": line_num,
            "expectedAnswer": "",
            "prediction": set(),
            "accuracy": 0.0,
            "is_correct": False,
            "error": "无法找到预测文本或目标答案字段"
        }
    
    line_num = record.get("lineInDataset", "未知")
    
    target_str = str(target)
    is_mcq = False
    
    if (
        len(target_str) == 1
        and target_str.isalpha()
        and target_str.isupper()
        and 'A' <= target_str <= 'Z'
    ):
        is_mcq = True
    elif ',' in target_str:
        parts = target_str.split(',')
        if all(
            len(p) == 1
            and p.isalpha()
            and p.isupper()
            and 'A' <= p <= 'Z'
            for p in parts
        ):
            is_mcq = True
    
    if is_mcq:
        if len(target_str) == 1:
            # Single choice question
            prediction = parse_answers(text)
            is_correct = target_str in prediction
            accuracy = 1.0 if is_correct else 0.0
            
            detail = {
                "lineInDataset": line_num,
                "expectedAnswer": target,
                "prediction": list(prediction),
                "accuracy": accuracy,
                "is_correct": is_correct,
                "question_type": "single_choice",
                "answer_text_last50": (
                    text[-50:] if len(text) > 50 else text
                )
            }
            
            if not is_correct:
                _print_mismatch_info(
                    line_num,
                    target_str,
                    prediction,
                    text[-50:] if len(text) > 50 else text,
                    verbose=verbose
                )
            
            return accuracy, detail
        else:
            # Multiple choice question
            prediction = parse_answers(
                text, DEFAULT_ANSWER_LENGTH, multiple_correct=True
            )
            den = len(
                parse_answers(
                    f"ANSWER: {target_str}",
                    DEFAULT_ANSWER_LENGTH,
                    multiple_correct=True
                )
            )
            if den == 0:
                msg = (
                    f"Target contains no options. target: {target_str}. "
                    f"This answer will be viewed as incorrect. "
                    f"(lineInDataset: {line_num})"
                )
                logger.warning(msg)
                return 0.0, {
                    "lineInDataset": line_num,
                    "expectedAnswer": target,
                    "prediction": list(prediction),
                    "accuracy": 0.0,
                    "is_correct": False,
                    "question_type": "multiple_choice",
                    "error": msg
                }
            num = 0
            for candidate in prediction:
                if candidate in target_str:
                    num += 1
            accuracy = num / den
            
            detail = {
                "lineInDataset": line_num,
                "expectedAnswer": target,
                "prediction": list(prediction),
                "accuracy": accuracy,
                "is_correct": accuracy == 1.0,
                "question_type": "multiple_choice",
                "partial_correct": num,
                "total_expected": den,
                "answer_text_last50": (
                    text[-50:] if len(text) > 50 else text
                )
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
            "answer_text_last50": (
                text[-50:] if len(text) > 50 else text
            )
        }
        
        if not is_correct:
            _print_mismatch_info(
                line_num,
                target,
                prediction_text,
                text[-50:] if len(text) > 50 else text,
                metric_name,
                verbose=verbose
            )
        
        return accuracy, detail
