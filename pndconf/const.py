from enum import IntEnum


class COLORS:
    """Color codes for terminal colors
    """
    RED = '\033[31m'
    ALT_RED = '\033[91m'
    BRIGHT_RED = '\033[1;31m'
    ALT_BRIGHT_RED = '\033[1;91m'
    YELLOW = '\033[33m'
    BRIGHT_YELLOW = '\033[1;33m'
    BLUE = '\033[34m'
    BRIGHT_BLUE = '\033[1;34m'
    ALT_BLUE = '\033[94m'
    ALT_BRIGHT_BLUE = '\033[1;94m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ENDC = '\033[0m'


class LogLevels(IntEnum):
    error = 0
    warning = 1
    info = 2
    debug = 3


gentypes = ["html", "pdf", "reveal", "beamer", "latex"]
log_levels = [x.name for x in LogLevels]
