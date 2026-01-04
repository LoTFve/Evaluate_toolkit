"""
从 agent.log 中提取每个 enhancement 方法的使用时间
"""
import re
import json
import os
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Any

# 正则表达式模式常量
UUID_PATTERN = r'\[([a-f0-9-]{36})\]'
TOOL_START_PATTERN = r'tool_enhancement_node.*?\[([a-f0-9-]{36})\].*?started'
KNOWLEDGE_START_PATTERN = r'knowledge_enhancement_method(\d+)_node.*?\[([a-f0-9-]{36})\].*?started'
KNOWLEDGE_END_PATTERN = r'knowledge_enhancement_method(\d+)_node.*?\[([a-f0-9-]{36})\].*?ended'
LLM_CALL_START_PATTERN = r'LLM call with tool messages \[([a-f0-9-]{36})\].*?started'
LLM_CALL_END_PATTERN = r'LLM call with tool messages \[([a-f0-9-]{36})\].*?ended'
NO_TOOLS_PATTERN = r'In \[([a-f0-9-]{36})\].*?No tools has been called'
TOOL_FINISHED_PATTERN = r'Tool calls in \[([a-f0-9-]{36})\].*?finished'
TOOL_ERROR_PATTERN = r'In \[([a-f0-9-]{36})\].*?Tool .*?failed'
DISCARD_PATTERN = r'Discarding method2 \[([a-f0-9-]{36})\].*?result due to'
TIMESTAMP_WITH_MS_PATTERN = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)'
TIMESTAMP_WITHOUT_MS_PATTERN = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'

# Enhancement 类型常量
TYPE_TOOL_FINISHED = 'tool_enhancement_finished'
TYPE_TOOL_FAILED = 'tool_enhancement_failed'
TYPE_TOOL_SKIPPED = 'tool_enhancement_skipped'
TYPE_TOOL_COMPLETE = 'tool_enhancement_complete'
TYPE_LLM_CALL = 'llm_call'
TYPE_KNOWLEDGE_METHOD1 = 'knowledge_enhancement_method1'
TYPE_KNOWLEDGE_METHOD2 = 'knowledge_enhancement_method2'

# 时间格式常量
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
TIMESTAMP_FORMAT_SIMPLE = '%Y-%m-%d %H:%M:%S'

# 显示格式常量
SEPARATOR_WIDTH = 80
PREVIEW_COUNT = 20
DECIMAL_PLACES = 3

# 统计字段名
FIELD_COUNT = 'count'
FIELD_TOTAL_TIME = 'total_time'
FIELD_AVG_TIME = 'avg_time'
FIELD_MIN_TIME = 'min_time'
FIELD_MAX_TIME = 'max_time'
FIELD_FAILED_COUNT = 'failed_count'


def _create_default_stat_entry() -> Dict[str, Any]:
    """创建默认的统计条目"""
    return {
        FIELD_COUNT: 0,
        FIELD_TOTAL_TIME: 0.0,
        FIELD_AVG_TIME: 0.0,
        FIELD_MIN_TIME: float('inf'),
        FIELD_MAX_TIME: 0.0,
        FIELD_FAILED_COUNT: 0
    }


def parse_timestamp(line: str) -> Optional[datetime]:
    """
    从日志行中解析时间戳
    
    Args:
        line: 日志行文本
        
    Returns:
        解析成功返回 datetime 对象，否则返回 None
    """
    # 尝试匹配带毫秒的时间戳
    time_match = re.search(TIMESTAMP_WITH_MS_PATTERN, line)
    if not time_match:
        # 尝试不带毫秒的时间戳
        time_match = re.search(TIMESTAMP_WITHOUT_MS_PATTERN, line)
        if time_match:
            timestamp_str = time_match.group(1) + '.0'
        else:
            return None
    else:
        timestamp_str = time_match.group(1)
    
    try:
        return datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
    except ValueError:
        try:
            return datetime.strptime(timestamp_str.split('.')[0], TIMESTAMP_FORMAT_SIMPLE)
        except (ValueError, IndexError):
            return None


def _create_enhancement_record(
    enh_type: str,
    start_time: datetime,
    end_time: datetime,
    start_line: int,
    end_line: int,
    node_id: str,
    **kwargs
) -> Dict[str, Any]:
    """
    创建 enhancement 记录
    
    Args:
        enh_type: enhancement 类型
        start_time: 开始时间
        end_time: 结束时间
        start_line: 开始行号
        end_line: 结束行号
        node_id: 节点ID
        **kwargs: 其他可选字段
        
    Returns:
        enhancement 记录字典
    """
    duration = (end_time - start_time).total_seconds()
    record = {
        'type': enh_type,
        'start_time': start_time,
        'end_time': end_time,
        'duration_seconds': duration,
        'start_line': start_line,
        'end_line': end_line,
        'node_id': node_id
    }
    record.update(kwargs)
    return record


def extract_enhancement_times(log_file: str) -> List[Dict[str, Any]]:
    """
    从日志文件中提取每个 enhancement 的使用时间
    
    Args:
        log_file: 日志文件路径
        
    Returns:
        每个 enhancement 的信息列表，包含类型、开始时间、结束时间、持续时间等
    """
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    enhancements = []
    
    # 用于跟踪当前活动的 enhancement
    active_tools: Dict[str, Dict[str, Any]] = {}
    active_knowledge: Dict[str, Dict[str, Dict[str, Any]]] = {}
    active_llm_calls: Dict[str, Dict[str, Any]] = {}
    last_finished_tool_id: Optional[str] = None
    finished_tool_map: Dict[str, Dict[str, Any]] = {}
    tool_skipped_ids: set = set()
    
    for i, line in enumerate(lines):
        timestamp = parse_timestamp(line)
        if timestamp is None:
            continue
        
        timestamp_str = timestamp.strftime(TIMESTAMP_FORMAT)
        
        # 检测 tool_enhancement 开始
        tool_start_match = re.search(TOOL_START_PATTERN, line)
        if tool_start_match:
            tool_id = tool_start_match.group(1)
            active_tools[tool_id] = {
                'line_num': i + 1,
                'timestamp_str': timestamp_str,
                'start_time': timestamp,
                'type': 'tool_enhancement',
                'id': tool_id
            }
        
        # 检测 "No tools has been called" 消息
        no_tools_match = re.search(NO_TOOLS_PATTERN, line)
        if no_tools_match:
            tool_id = no_tools_match.group(1)
            tool_skipped_ids.add(tool_id)
        
        # 匹配 finished 和 failed
        tool_end_id_match = re.search(TOOL_FINISHED_PATTERN, line)
        tool_error_match = re.search(TOOL_ERROR_PATTERN, line)
        
        matched_tool_id = None
        has_error = False
        is_skipped = False
        
        if tool_end_id_match:
            matched_tool_id = tool_end_id_match.group(1)
            if matched_tool_id in tool_skipped_ids:
                is_skipped = True
            has_error = False
        elif tool_error_match:
            matched_tool_id = tool_error_match.group(1)
            has_error = True
        
        if matched_tool_id and matched_tool_id in active_tools:
            tool = active_tools.pop(matched_tool_id)
            
            if is_skipped:
                enhancements.append(_create_enhancement_record(
                    TYPE_TOOL_SKIPPED,
                    tool['start_time'],
                    timestamp,
                    tool['line_num'],
                    i + 1,
                    matched_tool_id,
                    has_error=False
                ))
            elif has_error:
                enhancements.append(_create_enhancement_record(
                    TYPE_TOOL_FAILED,
                    tool['start_time'],
                    timestamp,
                    tool['line_num'],
                    i + 1,
                    matched_tool_id,
                    has_error=True
                ))
            else:
                tool_record = _create_enhancement_record(
                    TYPE_TOOL_FINISHED,
                    tool['start_time'],
                    timestamp,
                    tool['line_num'],
                    i + 1,
                    matched_tool_id,
                    has_error=False
                )
                enhancements.append(tool_record)
                last_finished_tool_id = matched_tool_id
                finished_tool_map[matched_tool_id] = tool_record
        
        # 检测 knowledge_enhancement 开始
        knowledge_start_match = re.search(KNOWLEDGE_START_PATTERN, line)
        if knowledge_start_match:
            method_num = knowledge_start_match.group(1)
            knowledge_id = knowledge_start_match.group(2)
            key = f'knowledge_enhancement_method{method_num}'
            if key not in active_knowledge:
                active_knowledge[key] = {}
            active_knowledge[key][knowledge_id] = {
                'line_num': i + 1,
                'timestamp_str': timestamp_str,
                'start_time': timestamp,
                'method_num': method_num,
                'id': knowledge_id
            }
        
        # 检测 knowledge_enhancement 结束
        knowledge_end_match = re.search(KNOWLEDGE_END_PATTERN, line)
        if knowledge_end_match:
            method_num = knowledge_end_match.group(1)
            knowledge_id = knowledge_end_match.group(2)
            key = f'knowledge_enhancement_method{method_num}'
            if key in active_knowledge and knowledge_id in active_knowledge[key]:
                knowledge = active_knowledge[key].pop(knowledge_id)
                duration = (timestamp - knowledge['start_time']).total_seconds()
                
                # 检查是否被 discard（对于 method2，discard 只可能出现在下一行）
                has_error = False
                if method_num == '2' and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    discard_match = re.search(DISCARD_PATTERN, next_line)
                    if discard_match and discard_match.group(1) == knowledge_id:
                        has_error = True
                
                enhancements.append(_create_enhancement_record(
                    f'knowledge_enhancement_method{method_num}',
                    knowledge['start_time'],
                    timestamp,
                    knowledge['line_num'],
                    i + 1,
                    knowledge_id,
                    has_error=has_error
                ))
        
        # 检测 LLM call 开始
        llm_call_start_match = re.search(LLM_CALL_START_PATTERN, line)
        if llm_call_start_match:
            llm_call_id = llm_call_start_match.group(1)
            tool_id = None
            
            # 检查前一行是否是 finished
            if i > 0 and last_finished_tool_id:
                prev_line = lines[i - 1]
                finished_match = re.search(TOOL_FINISHED_PATTERN, prev_line)
                if finished_match and finished_match.group(1) == last_finished_tool_id:
                    tool_id = last_finished_tool_id
                    last_finished_tool_id = None
            
            if llm_call_id not in active_llm_calls:
                active_llm_calls[llm_call_id] = {
                    'line_num': i + 1,
                    'timestamp_str': timestamp_str,
                    'start_time': timestamp,
                    'type': 'llm_call',
                    'id': llm_call_id,
                    'tool_id': tool_id
                }
            else:
                active_llm_calls[llm_call_id]['start_time'] = timestamp
                active_llm_calls[llm_call_id]['line_num'] = i + 1
                active_llm_calls[llm_call_id]['timestamp_str'] = timestamp_str
                if tool_id:
                    active_llm_calls[llm_call_id]['tool_id'] = tool_id
        
        # 检测 LLM call 结束
        llm_call_end_match = re.search(LLM_CALL_END_PATTERN, line)
        if llm_call_end_match:
            llm_call_id = llm_call_end_match.group(1)
            if llm_call_id in active_llm_calls:
                llm_call = active_llm_calls.pop(llm_call_id)
                llm_duration = (timestamp - llm_call['start_time']).total_seconds()
                
                if llm_call.get('start_time'):
                    llm_record = _create_enhancement_record(
                        TYPE_LLM_CALL,
                        llm_call['start_time'],
                        timestamp,
                        llm_call['line_num'],
                        i + 1,
                        llm_call_id,
                        tool_id=llm_call.get('tool_id')
                    )
                    enhancements.append(llm_record)
                    
                    # 如果有关联的 tool_id，创建 tool_enhancement_complete 记录
                    tool_id = llm_call.get('tool_id')
                    if tool_id and tool_id in finished_tool_map:
                        tool_record = finished_tool_map[tool_id]
                        total_duration = tool_record['duration_seconds'] + llm_duration
                        enhancements.append({
                            'type': TYPE_TOOL_COMPLETE,
                            'tool_id': tool_id,
                            'llm_id': llm_call_id,
                            'start_time': tool_record['start_time'],
                            'end_time': timestamp,
                            'duration_seconds': total_duration,
                            'tool_duration': tool_record['duration_seconds'],
                            'llm_duration': llm_duration,
                            'start_line': tool_record['start_line'],
                            'end_line': i + 1,
                            'node_id': tool_id
                        })
    
    # 记录未完成的 tool_enhancement（作为 skipped）
    for tool_id, tool in active_tools.items():
        enhancements.append(_create_enhancement_record(
            TYPE_TOOL_SKIPPED,
            tool['start_time'],
            tool['start_time'],
            tool['line_num'],
            tool['line_num'],
            tool_id,
            has_error=False
        ))
        # 设置持续时间为 0
        enhancements[-1]['duration_seconds'] = 0.0
    
    return enhancements


def _update_stat_entry(
    stats: Dict[str, Dict[str, Any]],
    key: str,
    duration: float,
    is_failed: bool = False
) -> None:
    """
    更新统计条目
    
    Args:
        stats: 统计字典
        key: 统计键
        duration: 持续时间
        is_failed: 是否失败
    """
    if key not in stats:
        stats[key] = _create_default_stat_entry()
    
    stat = stats[key]
    if is_failed:
        stat[FIELD_FAILED_COUNT] += 1
    else:
        stat[FIELD_COUNT] += 1
    
    stat[FIELD_TOTAL_TIME] += duration
    stat[FIELD_MIN_TIME] = min(stat[FIELD_MIN_TIME], duration)
    stat[FIELD_MAX_TIME] = max(stat[FIELD_MAX_TIME], duration)


def calculate_statistics(enhancements: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    计算 enhancement 的统计信息
    
    Args:
        enhancements: enhancement 记录列表
        
    Returns:
        包含各类型统计信息的字典
    """
    stats = {
        TYPE_TOOL_FINISHED: _create_default_stat_entry(),
        TYPE_TOOL_FAILED: _create_default_stat_entry(),
        TYPE_TOOL_SKIPPED: _create_default_stat_entry(),
        TYPE_TOOL_COMPLETE: _create_default_stat_entry(),
        TYPE_LLM_CALL: _create_default_stat_entry(),
        TYPE_KNOWLEDGE_METHOD1: _create_default_stat_entry(),
        TYPE_KNOWLEDGE_METHOD2: _create_default_stat_entry()
    }
    
    for enh in enhancements:
        enh_type = enh['type']
        duration = enh['duration_seconds']
        has_error = enh.get('has_error', False)
        
        if enh_type == TYPE_TOOL_FINISHED:
            _update_stat_entry(stats, TYPE_TOOL_FINISHED, duration, False)
        elif enh_type == TYPE_TOOL_FAILED:
            _update_stat_entry(stats, TYPE_TOOL_FAILED, duration, True)
        elif enh_type == TYPE_TOOL_SKIPPED:
            stats[TYPE_TOOL_SKIPPED][FIELD_COUNT] += 1
            # skipped 不计时间
        elif enh_type == TYPE_LLM_CALL:
            _update_stat_entry(stats, TYPE_LLM_CALL, duration, False)
        elif 'method1' in enh_type:
            _update_stat_entry(stats, TYPE_KNOWLEDGE_METHOD1, duration, False)
        elif 'method2' in enh_type:
            _update_stat_entry(stats, TYPE_KNOWLEDGE_METHOD2, duration, has_error)
        elif enh_type == TYPE_TOOL_COMPLETE:
            _update_stat_entry(stats, TYPE_TOOL_COMPLETE, duration, False)
    
    # 计算平均值
    for key in stats:
        stat = stats[key]
        total_count = stat[FIELD_COUNT] + stat[FIELD_FAILED_COUNT]
        if total_count > 0:
            stat[FIELD_AVG_TIME] = stat[FIELD_TOTAL_TIME] / total_count
            if stat[FIELD_MIN_TIME] == float('inf'):
                stat[FIELD_MIN_TIME] = 0.0
    
    return stats


def convert_to_json_record(enh: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 enhancement 记录转换为 JSON 格式（datetime 转为字符串）
    
    Args:
        enh: enhancement 记录字典
        
    Returns:
        转换后的 JSON 格式记录
    """
    record = {
        'type': enh['type'],
        'node_id': enh.get('node_id', ''),
        'start_time': enh['start_time'].strftime(TIMESTAMP_FORMAT),
        'end_time': enh['end_time'].strftime(TIMESTAMP_FORMAT),
        'duration_seconds': round(enh['duration_seconds'], DECIMAL_PLACES),
        'start_line': enh['start_line'],
        'end_line': enh['end_line']
    }
    
    # 添加可选字段
    optional_fields = ['has_error', 'tool_id', 'llm_id']
    for field in optional_fields:
        if field in enh:
            record[field] = enh[field]
    
    # 处理浮点数字段
    float_fields = ['tool_duration', 'llm_duration']
    for field in float_fields:
        if field in enh:
            record[field] = round(enh[field], DECIMAL_PLACES)
    
    return record


def calculate_stats_info(
    enhancement_list: List[Dict[str, Any]], 
    include_success_failed: bool = False
) -> Dict[str, Any]:
    """
    计算 enhancement 列表的统计信息
    
    Args:
        enhancement_list: enhancement 记录列表
        include_success_failed: 是否包含成功/失败统计
        
    Returns:
        统计信息字典
    """
    if not enhancement_list:
        return {}
    
    if include_success_failed:
        success_list = [enh for enh in enhancement_list if not enh.get('has_error', False)]
        failed_count = len(enhancement_list) - len(success_list)
        
        if success_list:
            avg_time = sum(enh['duration_seconds'] for enh in success_list) / len(success_list)
            total_time = sum(enh['duration_seconds'] for enh in success_list)
            return {
                '总数': len(enhancement_list),
                '成功数': len(success_list),
                '失败数': failed_count,
                '总时间(秒)': round(total_time, DECIMAL_PLACES),
                '平均时间(秒)': round(avg_time, DECIMAL_PLACES)
            }
        else:
            return {
                '总数': len(enhancement_list),
                '成功数': 0,
                '失败数': failed_count,
                '总时间(秒)': 0.0,
                '平均时间(秒)': 0.0
            }
    else:
        avg_time = sum(enh['duration_seconds'] for enh in enhancement_list) / len(enhancement_list)
        total_time = sum(enh['duration_seconds'] for enh in enhancement_list)
        return {
            '总数': len(enhancement_list),
            '总时间(秒)': round(total_time, DECIMAL_PLACES),
            '平均时间(秒)': round(avg_time, DECIMAL_PLACES)
        }


def save_enhancement_list_to_file(
    filepath: str,
    enhancement_list: List[Dict[str, Any]],
    stats_info: Optional[Dict[str, Any]] = None,
    include_success_failed: bool = False
) -> None:
    """
    将 enhancement 列表保存到 JSON 文件
    
    Args:
        filepath: 输出文件路径
        enhancement_list: enhancement 记录列表
        stats_info: 可选的统计信息字典，如果为 None 则自动计算
        include_success_failed: 是否在统计中包含成功/失败信息
    """
    if stats_info is None:
        stats_info = calculate_stats_info(enhancement_list, include_success_failed)
    
    records = [convert_to_json_record(enh) for enh in enhancement_list]
    output_data = {'统计信息': stats_info, '数据': records}
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


def _classify_enhancements(enhancements: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    将 enhancement 列表按类型分类
    
    Args:
        enhancements: enhancement 记录列表
        
    Returns:
        分类后的字典，键为类型名，值为该类型的记录列表
    """
    classified = {
        'tool_finished': [],
        'tool_failed': [],
        'tool_skipped': [],
        'tool_complete': [],
        'method1': [],
        'method2': [],
        'method2_discarded': [],
        'knowledge': [],
        'llm_call': [],
        'all': [],
        'all_success': []
    }
    
    for enh in enhancements:
        enh_type = enh['type']
        
        if enh_type == TYPE_TOOL_FINISHED:
            classified['tool_finished'].append(enh)
        elif enh_type == TYPE_TOOL_FAILED:
            classified['tool_failed'].append(enh)
            classified['all'].append(enh)
        elif enh_type == TYPE_TOOL_SKIPPED:
            classified['tool_skipped'].append(enh)
            classified['all'].append(enh)
        elif enh_type == TYPE_TOOL_COMPLETE:
            classified['tool_complete'].append(enh)
            classified['all'].append(enh)
            classified['all_success'].append(enh)
        elif enh_type == TYPE_LLM_CALL:
            classified['llm_call'].append(enh)
        elif enh_type == TYPE_KNOWLEDGE_METHOD1:
            classified['method1'].append(enh)
            classified['knowledge'].append(enh)
            classified['all'].append(enh)
            if not enh.get('has_error', False):
                classified['all_success'].append(enh)
        elif enh_type == TYPE_KNOWLEDGE_METHOD2:
            classified['method2'].append(enh)
            classified['knowledge'].append(enh)
            classified['all'].append(enh)
            if enh.get('has_error', False):
                classified['method2_discarded'].append(enh)
            else:
                classified['all_success'].append(enh)
    
    return classified


def _generate_output_file_path(input_dir: str, input_basename: str, suffix: str) -> str:
    """
    生成输出文件路径
    
    Args:
        input_dir: 输入目录
        input_basename: 输入文件基础名（不含扩展名）
        suffix: 文件后缀
        
    Returns:
        输出文件完整路径
    """
    return os.path.join(input_dir, f'{input_basename}{suffix}')


def _print_statistics_table(stats: Dict[str, Dict[str, Any]]) -> None:
    """
    打印统计信息表格
    
    Args:
        stats: 统计信息字典
    """
    print("\n统计信息（仅统计成功的事件）:")
    print("-" * SEPARATOR_WIDTH)
    print(f"{'类型':<30} {'成功次数':<12} {'失败次数':<12} {'总时间(秒)':<15} "
          f"{'平均时间(秒)':<15} {'最小时间(秒)':<15} {'最大时间(秒)':<15}")
    print("-" * SEPARATOR_WIDTH)
    
    for key, stat in stats.items():
        if stat[FIELD_COUNT] > 0 or stat[FIELD_FAILED_COUNT] > 0:
            print(f"{key:<30} {stat[FIELD_COUNT]:<12} {stat[FIELD_FAILED_COUNT]:<12} "
                  f"{stat[FIELD_TOTAL_TIME]:<15.2f} {stat[FIELD_AVG_TIME]:<15.2f} "
                  f"{stat[FIELD_MIN_TIME]:<15.2f} {stat[FIELD_MAX_TIME]:<15.2f}")


def _print_preview(enhancements: List[Dict[str, Any]]) -> None:
    """
    打印前 N 个 enhancement 事件预览
    
    Args:
        enhancements: enhancement 记录列表
    """
    print(f"\n前{PREVIEW_COUNT}个 enhancement 事件:")
    print("-" * SEPARATOR_WIDTH)
    print(f"{'序号':<6} {'ID号':<40} {'类型':<30} {'开始时间':<20} "
          f"{'持续时间(秒)':<15} {'起始行':<10}")
    print("-" * SEPARATOR_WIDTH)
    
    for i, enh in enumerate(enhancements[:PREVIEW_COUNT], 1):
        start_time_str = enh['start_time'].strftime(TIMESTAMP_FORMAT_SIMPLE)
        node_id = enh.get('node_id', 'N/A')
        print(f"{i:<6} {str(node_id):<40} {enh['type']:<30} {start_time_str:<20} "
              f"{enh['duration_seconds']:<15.2f} {enh['start_line']:<10}")


def _build_summary_statistics(stats: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    构建汇总统计信息
    
    Args:
        stats: 各类型统计信息
        
    Returns:
        包含汇总统计的字典
    """
    stats_output = {}
    
    # 添加各类型统计
    for key, stat in stats.items():
        if stat[FIELD_COUNT] > 0 or stat[FIELD_FAILED_COUNT] > 0:
            stat_dict = {
                '总时间(秒)': round(stat[FIELD_TOTAL_TIME], DECIMAL_PLACES),
                '平均时间(秒)': round(stat[FIELD_AVG_TIME], DECIMAL_PLACES),
                '最小时间(秒)': round(stat[FIELD_MIN_TIME], DECIMAL_PLACES),
                '最大时间(秒)': round(stat[FIELD_MAX_TIME], DECIMAL_PLACES)
            }
            
            if key == TYPE_TOOL_SKIPPED:
                stat_dict['跳过次数'] = stat[FIELD_COUNT]
                stat_dict['成功次数'] = 0
                stat_dict['失败次数'] = 0
            else:
                stat_dict['成功次数'] = stat[FIELD_COUNT]
                stat_dict['失败次数'] = stat[FIELD_FAILED_COUNT]
                stat_dict['跳过次数'] = 0
            
            stats_output[key] = stat_dict
    
    # tool_enhancement 汇总
    tool_total_count = (
        stats[TYPE_TOOL_FINISHED][FIELD_COUNT] +
        stats[TYPE_TOOL_FAILED][FIELD_FAILED_COUNT] +
        stats[TYPE_TOOL_SKIPPED][FIELD_COUNT] +
        stats[TYPE_TOOL_COMPLETE][FIELD_COUNT]
    )
    tool_total_failed = stats[TYPE_TOOL_FAILED][FIELD_FAILED_COUNT]
    tool_total_time = (
        stats[TYPE_TOOL_FINISHED][FIELD_TOTAL_TIME] +
        stats[TYPE_TOOL_FAILED][FIELD_TOTAL_TIME] +
        stats[TYPE_TOOL_COMPLETE][FIELD_TOTAL_TIME]
    )
    tool_total_success = (
        stats[TYPE_TOOL_FINISHED][FIELD_COUNT] +
        stats[TYPE_TOOL_COMPLETE][FIELD_COUNT]
    )
    
    stats_output['tool_enhancement_汇总'] = {
        '总数': tool_total_count,
        '成功次数': tool_total_success,
        '失败次数': tool_total_failed,
        '跳过次数': stats[TYPE_TOOL_SKIPPED][FIELD_COUNT],
        '总时间(秒)': round(tool_total_time, DECIMAL_PLACES),
        '平均时间(秒)': round(tool_total_time / tool_total_count, DECIMAL_PLACES) if tool_total_count > 0 else 0.0
    }
    
    # knowledge_enhancement 汇总
    knowledge_total_count = (
        stats[TYPE_KNOWLEDGE_METHOD1][FIELD_COUNT] +
        stats[TYPE_KNOWLEDGE_METHOD1][FIELD_FAILED_COUNT] +
        stats[TYPE_KNOWLEDGE_METHOD2][FIELD_COUNT] +
        stats[TYPE_KNOWLEDGE_METHOD2][FIELD_FAILED_COUNT]
    )
    knowledge_total_success = (
        stats[TYPE_KNOWLEDGE_METHOD1][FIELD_COUNT] +
        stats[TYPE_KNOWLEDGE_METHOD2][FIELD_COUNT]
    )
    knowledge_total_failed = (
        stats[TYPE_KNOWLEDGE_METHOD1][FIELD_FAILED_COUNT] +
        stats[TYPE_KNOWLEDGE_METHOD2][FIELD_FAILED_COUNT]
    )
    knowledge_total_time = (
        stats[TYPE_KNOWLEDGE_METHOD1][FIELD_TOTAL_TIME] +
        stats[TYPE_KNOWLEDGE_METHOD2][FIELD_TOTAL_TIME]
    )
    
    stats_output['knowledge_enhancement_汇总'] = {
        '总数': knowledge_total_count,
        '成功次数': knowledge_total_success,
        '失败次数': knowledge_total_failed,
        '总时间(秒)': round(knowledge_total_time, DECIMAL_PLACES),
        '平均时间(秒)': round(knowledge_total_time / knowledge_total_count, DECIMAL_PLACES) if knowledge_total_count > 0 else 0.0
    }
    
    # 所有类型总计
    all_total_count = sum(stat[FIELD_COUNT] + stat[FIELD_FAILED_COUNT] for stat in stats.values())
    all_total_success = sum(
        stat[FIELD_COUNT] for key, stat in stats.items() 
        if key != TYPE_TOOL_SKIPPED
    )
    all_total_failed = sum(stat[FIELD_FAILED_COUNT] for stat in stats.values())
    all_total_skipped = stats[TYPE_TOOL_SKIPPED][FIELD_COUNT]
    all_total_time = sum(stat[FIELD_TOTAL_TIME] for stat in stats.values())
    
    stats_output['总计'] = {
        '总数': all_total_count,
        '成功次数': all_total_success,
        '失败次数': all_total_failed,
        '跳过次数': all_total_skipped,
        '总时间(秒)': round(all_total_time, DECIMAL_PLACES),
        '平均时间(秒)': round(all_total_time / all_total_count, DECIMAL_PLACES) if all_total_count > 0 else 0.0
    }
    
    return stats_output


def _save_all_output_files(
    input_dir: str,
    input_basename: str,
    classified: Dict[str, List[Dict[str, Any]]],
    stats: Dict[str, Dict[str, Any]]
) -> None:
    """
    保存所有输出文件
    
    Args:
        input_dir: 输入目录
        input_basename: 输入文件基础名
        classified: 分类后的 enhancement 列表
        stats: 统计信息
    """
    # 生成所有文件路径
    file_paths = {
        'tool_complete': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_tool_complete.json'),
        'tool_finished': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_tool_finished.json'),
        'tool_failed': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_tool_failed.json'),
        'tool_skipped': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_tool_skipped.json'),
        'llm_call': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_llm_call.json'),
        'method1': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_method1.json'),
        'method2': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_method2.json'),
        'method2_discarded': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_method2_discarded.json'),
        'knowledge': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_knowledge.json'),
        'all': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_all.json'),
        'all_success': _generate_output_file_path(input_dir, input_basename, '_enhancement_times_all_success.json')
    }
    
    # 保存 tool_enhancement_complete
    stats_info = {}
    if classified['tool_complete']:
        tool_complete_list = classified['tool_complete']
        avg_time = sum(enh['duration_seconds'] for enh in tool_complete_list) / len(tool_complete_list)
        total_time = sum(enh['duration_seconds'] for enh in tool_complete_list)
        avg_tool_time = sum(enh['tool_duration'] for enh in tool_complete_list) / len(tool_complete_list)
        avg_llm_time = sum(enh['llm_duration'] for enh in tool_complete_list) / len(tool_complete_list)
        stats_info = {
            '总数': len(tool_complete_list),
            '总时间(秒)': round(total_time, DECIMAL_PLACES),
            '平均时间(秒)': round(avg_time, DECIMAL_PLACES),
            'tool_enhancement平均时间(秒)': round(avg_tool_time, DECIMAL_PLACES),
            'llm_call平均时间(秒)': round(avg_llm_time, DECIMAL_PLACES)
        }
    save_enhancement_list_to_file(file_paths['tool_complete'], classified['tool_complete'], stats_info)
    
    # 保存其他文件
    save_enhancement_list_to_file(file_paths['tool_finished'], classified['tool_finished'])
    save_enhancement_list_to_file(file_paths['tool_failed'], classified['tool_failed'])
    
    # 保存 tool_enhancement_skipped
    stats_info = {}
    if classified['tool_skipped']:
        stats_info = {
            '总数': len(classified['tool_skipped']),
            '总时间(秒)': 0.0,
            '平均时间(秒)': 0.0,
            '说明': 'skipped 事件不计入时间统计'
        }
    save_enhancement_list_to_file(file_paths['tool_skipped'], classified['tool_skipped'], stats_info)
    
    save_enhancement_list_to_file(file_paths['llm_call'], classified['llm_call'])
    save_enhancement_list_to_file(file_paths['method1'], classified['method1'], include_success_failed=True)
    
    # 保存 method2（只保存成功的）
    method2_success_list = [enh for enh in classified['method2'] if not enh.get('has_error', False)]
    stats_info = calculate_stats_info(method2_success_list)
    if stats_info:
        stats_info['说明'] = '只包含成功的记录'
    save_enhancement_list_to_file(file_paths['method2'], method2_success_list, stats_info)
    
    # 保存 method2_discarded
    stats_info = calculate_stats_info(classified['method2_discarded'])
    if stats_info:
        stats_info['说明'] = '全部被discard，但时间仍计入统计'
    save_enhancement_list_to_file(file_paths['method2_discarded'], classified['method2_discarded'], stats_info)
    
    save_enhancement_list_to_file(file_paths['knowledge'], classified['knowledge'], include_success_failed=True)
    save_enhancement_list_to_file(file_paths['all'], classified['all'], include_success_failed=True)
    
    # 保存所有成功的记录
    stats_info = calculate_stats_info(classified['all_success'])
    if stats_info:
        stats_info['说明'] = '只包含成功的记录'
    save_enhancement_list_to_file(file_paths['all_success'], classified['all_success'], stats_info)
    
    # 打印文件列表
    print(f"\n已生成11个JSON文件:")
    print(f"  1. {file_paths['tool_complete']} - tool_enhancement (finished + llm_call, {len(classified['tool_complete'])} 条)")
    print(f"  2. {file_paths['tool_finished']} - tool_enhancement_finished ({len(classified['tool_finished'])} 条)")
    print(f"  3. {file_paths['tool_failed']} - tool_enhancement_failed ({len(classified['tool_failed'])} 条)")
    print(f"  4. {file_paths['tool_skipped']} - tool_enhancement_skipped ({len(classified['tool_skipped'])} 条)")
    print(f"  5. {file_paths['llm_call']} - llm_call ({len(classified['llm_call'])} 条)")
    print(f"  6. {file_paths['method1']} - knowledge_enhancement_method1 ({len(classified['method1'])} 条)")
    print(f"  7. {file_paths['method2']} - knowledge_enhancement_method2 成功 ({len(method2_success_list)} 条)")
    print(f"  8. {file_paths['method2_discarded']} - knowledge_enhancement_method2 被discard ({len(classified['method2_discarded'])} 条)")
    print(f"  9. {file_paths['knowledge']} - knowledge_enhancement (method1 + method2, {len(classified['knowledge'])} 条)")
    print(f"  10. {file_paths['all']} - 所有类型汇总 ({len(classified['all'])} 条)")
    print(f"  11. {file_paths['all_success']} - 所有成功类型汇总 ({len(classified['all_success'])} 条)")


def main() -> None:
    """主函数：解析命令行参数并执行提取"""
    parser = argparse.ArgumentParser(description="从 agent.log 中提取每个 enhancement 方法的使用时间")
    parser.add_argument(
        "log_file",
        type=str,
        nargs='?',
        default='ninth/ninth_agent.log',
        help="日志文件路径（默认: ninth/ninth_agent.log）"
    )
    args = parser.parse_args()
    
    log_file = args.log_file
    
    # 从输入文件路径提取目录和文件名
    input_abs_path = os.path.abspath(log_file)
    input_dir = os.path.dirname(input_abs_path)
    input_basename = os.path.splitext(os.path.basename(input_abs_path))[0]
    
    # 如果输入文件在根目录，input_dir 为空字符串，需要处理
    if not input_dir:
        input_dir = os.getcwd()
    
    print("提取 enhancement 使用时间")
    print("=" * SEPARATOR_WIDTH)
    
    enhancements = extract_enhancement_times(log_file)
    print(f"\n总共提取到 {len(enhancements)} 个 enhancement 事件")
    
    # 分类 enhancement
    classified = _classify_enhancements(enhancements)
    
    print(f"\n分类统计:")
    print(f"  tool_enhancement_finished: {len(classified['tool_finished'])} 个")
    print(f"  tool_enhancement_failed: {len(classified['tool_failed'])} 个")
    print(f"  tool_enhancement_skipped: {len(classified['tool_skipped'])} 个")
    print(f"  llm_call: {len(classified['llm_call'])} 个")
    print(f"  knowledge_enhancement_method1: {len(classified['method1'])} 个")
    print(f"  knowledge_enhancement_method2: {len(classified['method2'])} 个")
    print(f"  knowledge_enhancement (method1+method2): {len(classified['knowledge'])} 个")
    print(f"  总计: {len(classified['all'])} 个")
    
    # 计算统计信息
    stats = calculate_statistics(enhancements)
    _print_statistics_table(stats)
    _print_preview(enhancements)
    
    # 保存统计信息
    stats_file = _generate_output_file_path(input_dir, input_basename, '_enhancement_statistics.json')
    stats_output = _build_summary_statistics(stats)
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats_output, f, ensure_ascii=False, indent=2)
    
    # 保存所有输出文件
    _save_all_output_files(input_dir, input_basename, classified, stats)
    
    print(f"\n统计信息已保存到 {stats_file} (JSON格式)")


if __name__ == '__main__':
    main()
