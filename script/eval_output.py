"""评估模型输出结果的模块。

该模块提供了多种评估函数，用于处理选择题（MCQ）和填空题的答案评估。
支持单选题、多选题、Yes/No题目和数值题目的评估。

主脚本：调用各个独立模块完成评估流程
"""

import argparse
import json
import os
from typing import Any

from loguru import logger

from utils.eval_utils import process_line


def main() -> None:
    """主函数：处理评估文件并生成评估结果。
    
    从输入的 JSONL 文件中读取记录，评估每条记录的正确率，
    并生成包含统计信息和详细结果的 JSON 文件。
    """
    parser = argparse.ArgumentParser(description="评估模型输出结果")
    parser.add_argument("file_path", type=str, help="输入 JSONL 文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", default=False, help="是否输出打印信息（默认不输出）")
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
                    acc, detail = process_line(record, verbose=args.verbose)
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
    if args.verbose:
        print(f"\n总题目数: {total_count}")
        print(f"正确数: {correct_count}")
        print(f"错误数: {total_count - correct_count}")
        print(f"总体正确率: {overall_accuracy:.4f} ({overall_accuracy * 100:.2f}%)")
        print(f"\n详细结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
