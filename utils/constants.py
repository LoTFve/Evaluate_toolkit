"""
常量定义模块
包含所有路径类型、字段名、显示格式等常量
"""

# 路径类型常量
PATH_TYPE_TOOL = 'tool'
PATH_TYPE_KNOWLEDGE = 'knowledge'
PATH_TYPE_UNKNOWN = 'unknown'

# 显示格式常量
SEPARATOR_WIDTH = 100
PATH_NAME_WIDTH = 20
NUMBER_WIDTH = 18
ANSWER_MAX_LENGTH = 50

# 统计字段名
FIELD_CORRECT = 'correct'
FIELD_TOTAL = 'total'
FIELD_ACCURACY = 'accuracy'
FIELD_LINE_NUMBERS = 'line_numbers'
FIELD_CORRECT_LINE_NUMBERS = 'correct_line_numbers'
FIELD_INCORRECT_LINE_NUMBERS = 'incorrect_line_numbers'

# 题目类型统计字段名
FIELD_MCQ_CORRECT = 'mcq_correct'
FIELD_MCQ_TOTAL = 'mcq_total'
FIELD_MCQ_ACCURACY = 'mcq_accuracy'
FIELD_NONMCQ_CORRECT = 'nonmcq_correct'
FIELD_NONMCQ_TOTAL = 'nonmcq_total'
FIELD_NONMCQ_ACCURACY = 'nonmcq_accuracy'
FIELD_YESNO_CORRECT = 'yesno_correct'
FIELD_YESNO_TOTAL = 'yesno_total'
FIELD_YESNO_ACCURACY = 'yesno_accuracy'
FIELD_NUMERIC_CORRECT = 'numeric_correct'
FIELD_NUMERIC_TOTAL = 'numeric_total'
FIELD_NUMERIC_ACCURACY = 'numeric_accuracy'

# 填空题类型常量
NONMCQ_TYPE_YESNO = 'yesno'
NONMCQ_TYPE_NUMERIC = 'numeric'

# JSON 字段名
JSON_FIELD_QUESTION = 'question'
JSON_FIELD_TOOL = 'tool'
JSON_FIELD_KNOWLEDGE = 'knowledge'
JSON_FIELD_MESSAGES = 'messages'
JSON_FIELD_ROLE = 'role'
JSON_FIELD_TOOL_CALLS = 'tool_calls'
JSON_FIELD_FUNCTION = 'function'
JSON_FIELD_NAME = 'name'
JSON_FIELD_LINE_IN_DATASET = 'lineInDataset'
JSON_FIELD_EXPECTED_ANSWER = 'expectedAnswer'
JSON_FIELD_ANSWER = 'answer'
JSON_FIELD_TOOLS_USED = 'tools_used'
JSON_FIELD_PATH_TYPE = 'path_type'
JSON_FIELD_TOOLS = 'tools'
