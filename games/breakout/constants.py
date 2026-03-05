from constants import SCREEN_WIDTH

PADDLE_WIDTH  = 110
PADDLE_HEIGHT = 14
PADDLE_SPEED  = 500
PADDLE_Y      = 660   # fixed Y position

BALL_RADIUS   = 7
BALL_SPEED    = 380
BALL_MAX_SPEED = 600
BALL_SPEEDUP  = 5

BRICK_COLS    = 12
BRICK_ROWS    = 7
BRICK_WIDTH   = 80
BRICK_HEIGHT  = 24
BRICK_PADDING = 4
BRICK_TOP_Y   = 80    # Y of first brick row
BRICK_START_X = (SCREEN_WIDTH - BRICK_COLS * (BRICK_WIDTH + BRICK_PADDING)) // 2

PLAYER_LIVES  = 3

# Row colors are assigned in game.py using the colors module
ROW_COLORS = None
