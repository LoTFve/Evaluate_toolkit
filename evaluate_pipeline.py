"""
评估流水线：自动运行所有评估脚本
支持指定输入目录，自动运行四个评估步骤：
1. eval_output.py - 评估结果文件
2. extract_enhancement_time.py - 提取增强时间
3. calculate_accuracy_by_path.py - 按路径计算准确率
4. statistics_by_tool.py - 按工具统计
"""
import os
import sys
import json
import subprocess
import argparse
from pathlib import Path


def run_eval_output(input_dir: str, result_file: str) -> bool:
    """
    运行 eval_output.py 评估结果文件
    
    Args:
        input_dir: 输入目录
        result_file: 结果文件路径
        
    Returns:
        bool: 是否成功
    """
    print("\n" + "=" * 80)
    print("步骤 1/4: 运行 eval_output.py")
    print("=" * 80)
    
    if not os.path.exists(result_file):
        print(f"跳过: 文件不存在 {result_file}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, "eval_output.py", result_file],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"错误: {e}")
        return False


def run_extract_enhancement_time(input_dir: str, log_file: str) -> bool:
    """
    运行 extract_enhancement_time.py 提取增强时间
    
    Args:
        input_dir: 输入目录
        log_file: 日志文件路径
        
    Returns:
        bool: 是否成功
    """
    print("\n" + "=" * 80)
    print("步骤 2/4: 运行 extract_enhancement_time.py")
    print("=" * 80)
    
    if not os.path.exists(log_file):
        print(f"跳过: 文件不存在 {log_file}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, "extract_enhancement_time.py", log_file],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"错误: {e}")
        return False


def run_calculate_accuracy_by_path(input_dir: str, dump_file: str, result_file: str) -> bool:
    """
    运行 calculate_accuracy_by_path.py 按路径计算准确率
    
    Args:
        input_dir: 输入目录
        dump_file: thirdgen_dump.jsonl 文件路径
        result_file: result.jsonl 文件路径
        
    Returns:
        bool: 是否成功
    """
    print("\n" + "=" * 80)
    print("步骤 3/4: 运行 calculate_accuracy_by_path.py")
    print("=" * 80)
    
    if not os.path.exists(dump_file):
        print(f"跳过: 文件不存在 {dump_file}")
        return False
    if not os.path.exists(result_file):
        print(f"跳过: 文件不存在 {result_file}")
        return False
    
    try:
        result = subprocess.run(
            [
                sys.executable, 
                "calculate_accuracy_by_path.py",
                "--dump_file", dump_file,
                "--result_file", result_file
            ],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"错误: {e}")
        return False


def run_statistics_by_tool(input_dir: str, accuracy_file: str) -> bool:
    """
    运行 statistics_by_tool.py 按工具统计
    
    Args:
        input_dir: 输入目录
        accuracy_file: accuracy_by_path.json 文件路径
        
    Returns:
        bool: 是否成功
    """
    print("\n" + "=" * 80)
    print("步骤 4/4: 运行 statistics_by_tool.py")
    print("=" * 80)
    
    if not os.path.exists(accuracy_file):
        print(f"跳过: 文件不存在 {accuracy_file}（需要先运行 calculate_accuracy_by_path.py）")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, "statistics_by_tool.py", accuracy_file],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"错误: {e}")
        return False


def evaluate_pipeline(input_dir: str):
    """
    运行完整的评估流水线
    
    Args:
        input_dir: 输入目录路径（可以是绝对路径、相对路径，如 "ninth" 或 "C:\\path\\to\\ninth"）
    """
    # 处理输入目录路径：支持绝对路径和相对路径
    if os.path.isabs(input_dir):
        # 绝对路径
        input_path = input_dir
    else:
        # 相对路径：先尝试相对于当前工作目录，再尝试相对于脚本目录
        if os.path.exists(input_dir):
            input_path = os.path.abspath(input_dir)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            input_path = os.path.join(base_dir, input_dir)
    
    # 标准化路径（处理 .. 和 . 等）
    input_path = os.path.normpath(os.path.abspath(input_path))
    
    if not os.path.exists(input_path):
        print(f"错误: 输入目录不存在: {input_path}")
        return
    
    if not os.path.isdir(input_path):
        print(f"错误: 输入路径不是目录: {input_path}")
        return
    
    # 确定文件名前缀（从目录名提取，如 "ninth" -> "ninth"）
    dir_name = os.path.basename(input_path.rstrip(os.sep))
    
    # 构建文件路径
    result_file = os.path.join(input_path, f"{dir_name}_result.jsonl")
    log_file = os.path.join(input_path, f"{dir_name}_agent.log")
    dump_file = os.path.join(input_path, f"{dir_name}_thirdgen_dump.jsonl")
    accuracy_file = os.path.join(input_path, f"{dir_name}_accuracy_by_path.json")
    
    print("=" * 80)
    print(f"开始运行评估流水线: {input_dir}")
    print("=" * 80)
    print(f"输入目录: {input_path}")
    print(f"结果文件: {result_file}")
    print(f"日志文件: {log_file}")
    print(f"增强路径文件: {dump_file}")
    print("=" * 80)
    
    # 检查必需文件
    required_files = {
        "结果文件": result_file,
        "日志文件": log_file,
        "增强路径文件": dump_file
    }
    
    print("\n检查必需文件...")
    for name, path in required_files.items():
        if os.path.exists(path):
            print(f"  [OK] {name}: {path}")
        else:
            print(f"  [X] {name}: {path} (不存在)")
    
    results = {}
    
    # 步骤 1: eval_output.py
    results['eval_output'] = run_eval_output(input_path, result_file)
    
    # 步骤 2: extract_enhancement_time.py
    results['extract_enhancement_time'] = run_extract_enhancement_time(input_path, log_file)
    
    # 步骤 3: calculate_accuracy_by_path.py
    results['calculate_accuracy_by_path'] = run_calculate_accuracy_by_path(
        input_path, dump_file, result_file
    )
    
    # 步骤 4: statistics_by_tool.py
    results['statistics_by_tool'] = run_statistics_by_tool(input_path, accuracy_file)
    
    # 打印总结
    print("\n" + "=" * 80)
    print("评估流水线执行总结")
    print("=" * 80)
    for step, success in results.items():
        status = "[OK] 成功" if success else "[X] 失败/跳过"
        print(f"  {step}: {status}")
    print("=" * 80)
    
    # 输出文件位置
    print(f"\n输出文件位置: {input_path}")
    print("\n生成的文件:")
    output_files = [
        f"{dir_name}_result_eval_result.json",
        f"{dir_name}_agent_enhancement_statistics.json",
        f"{dir_name}_accuracy_by_path.json",
        f"{dir_name}_accuracy_by_path_statistics_by_tool.json",
        f"{dir_name}_accuracy_by_path_knowledge_questions.json"
    ]
    for filename in output_files:
        filepath = os.path.join(input_path, filename)
        if os.path.exists(filepath):
            print(f"  [OK] {filename}")
        else:
            print(f"  - {filename} (未生成)")


def main():
    parser = argparse.ArgumentParser(
        description="评估流水线：自动运行所有评估脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用相对路径（相对于当前工作目录或脚本目录）
  python evaluate_pipeline.py ninth
  python evaluate_pipeline.py ./ninth
  
  # 使用绝对路径
  python evaluate_pipeline.py C:\\Users\\honor\\Desktop\\thrid_model_analyse\\ninth
  
  # 使用当前目录
  cd ninth
  python ../evaluate_pipeline.py .
        """
    )
    parser.add_argument(
        "input_dir",
        type=str,
        help="输入目录路径（可以是绝对路径或相对路径，如 ninth 或 C:\\path\\to\\ninth）"
    )
    args = parser.parse_args()
    
    evaluate_pipeline(args.input_dir)


if __name__ == "__main__":
    main()
