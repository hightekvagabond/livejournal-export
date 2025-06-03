import os
import logging
import re
import traceback
from typing import Optional

class CompactTracebackFormatter(logging.Formatter):
    def formatException(self, exc_info):
        """
        Format an exception so that it prints on one line and is easier to read.
        """
        if not exc_info:
            return ""
        
        tb_lines = traceback.format_exception(exc_info[0], exc_info[1], exc_info[2])
        # Remove extra newlines and leading/trailing whitespace from each line
        # And join them with a clear separator
        formatted_traceback = " -> ".join([line.strip().replace('\n', '') for line in tb_lines])
        # Remove excessive repeated whitespace
        formatted_traceback = re.sub(r'\s+', ' ', formatted_traceback)
        return formatted_traceback

    def format(self, record):
        s = super().format(record)
        if record.exc_info:
            # Append the custom formatted exception
            # Ensure it's on a new line for clarity, but part of the same log event
            s += "\n" + self.formatException(record.exc_info)
        return s

class CleanOutputHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.whitespace_pattern = re.compile(r'\s\s+') # Matches two or more spaces

    def emit(self, record):
        try:
            msg = self.format(record)
            # Clean up the message by removing excessive whitespace from the main message part
            # The formatter now handles exception formatting
            
            # Split message and traceback if present
            if "\n" in msg and record.exc_info:
                main_msg_part, tb_part = msg.split("\n", 1)
                main_msg_part = self.whitespace_pattern.sub(' ', main_msg_part).strip()
                # Traceback part is already formatted by CompactTracebackFormatter
                cleaned_msg = f"{main_msg_part}\n{tb_part}"
            else:
                cleaned_msg = self.whitespace_pattern.sub(' ', msg).strip()
            
            # Print with a leading newline for separation from other terminal output
            print(f"\n{cleaned_msg}", flush=True)
        except Exception:
            self.handleError(record)

def setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Set up a logger with the specified name and debug level.
    
    Args:
        name: The name of the logger
        level: Debug level (0=quiet, 1=info, 2=verbose, 3=debug)
    
    Returns:
        A configured logger instance
    """
    level_map = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.INFO, 
        3: logging.DEBUG
    }
    
    if level is None:
        level = int(os.getenv('DEBUG_LEVEL', '0'))
    
    logger = logging.getLogger(name)
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(level_map.get(level, logging.WARNING))
    
    handler = CleanOutputHandler()
    # Use the custom formatter for both regular messages and exceptions
    formatter = CompactTracebackFormatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

def get_debug_level() -> int:
    return int(os.getenv('DEBUG_LEVEL', '0')) 