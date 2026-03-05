BOARD_COLS   = 10
BOARD_ROWS   = 20
CELL_SIZE    = 32

BOARD_WIDTH  = BOARD_COLS * CELL_SIZE    # 320
BOARD_HEIGHT = BOARD_ROWS * CELL_SIZE    # 640

# Center board on screen, shifted left to leave room for sidebar
BOARD_X = (1280 - BOARD_WIDTH) // 2 - 80
BOARD_Y = (720 - BOARD_HEIGHT) // 2

# Scoring (standard Tetris)
SCORE_TABLE  = {1: 100, 2: 300, 3: 500, 4: 800}
LEVEL_LINES  = 10      # lines to clear per level up
SPRINT_LINES = 40      # target for sprint mode
ULTRA_TIME   = 120.0   # seconds for ultra mode

# Drop speed: seconds per row drop per level (decreasing)
def drop_interval(level: int) -> float:
    return max(0.05, 0.8 - (level - 1) * 0.07)
