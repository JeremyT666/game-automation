import logging
import os
import sys
from datetime import datetime
from logging import FileHandler
from pathlib import Path

import colorlog

# get the project root directory
project_root = Path(__file__).parent.parent.parent  # src/utils -> src -> 項目根目錄
logs_dir = project_root / "reports" / "logs"
os.makedirs(logs_dir, exist_ok=True)  # 確保日誌目錄存在

# 生成時間戳格式的字符串
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
log_filename = f"autotest_{timestamp}.log"
log_file_path = logs_dir / log_filename

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# 設置console log的顏色
console_formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s %(levelname)s %(message)s",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    }
)

# console log handle
console_handler = logging.StreamHandler(sys.stdout) # output to sys.stdout
console_handler.setFormatter(console_formatter)
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

# logger formatter setup
file_formatter = logging.Formatter("%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s")

# 將執行log寫入out{timestamp}.log中
file_handler = FileHandler(str(log_file_path), mode="w")
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

# log file path
# logger.info(f"Log file created at: {log_file_path}")


# 導出 logger 供其他模組使用
__all__ = ['logger']