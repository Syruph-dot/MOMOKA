from datetime import datetime
from agents import function_tool

@function_tool
def get_current_time() -> str:
    """返回当前日期和时间（北京时间）。不需要任何参数。"""
    now = datetime.now()
    return now.strftime("%Y年%m月%d日 %H:%M:%S (星期%w)")
