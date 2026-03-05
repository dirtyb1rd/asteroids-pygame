CELL_SIZE    = 20
GRID_COLS    = 40      # 40 * 20 = 800px game area
GRID_ROWS    = 32      # 32 * 20 = 640px game area

# Position the grid centered on screen
GRID_OFFSET_X = (1280 - GRID_COLS * CELL_SIZE) // 2
GRID_OFFSET_Y = (720  - GRID_ROWS * CELL_SIZE) // 2

BASE_TICK    = 0.13    # seconds per snake step
SPEED_RAMP   = 5       # every N food, speed increases
TICK_DECREASE = 0.008  # reduce tick interval by this per ramp
MIN_TICK     = 0.04    # minimum tick interval

SPEEDRUN_GOAL = 30     # food items to eat in speed run mode
