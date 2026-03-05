PADDLE_WIDTH  = 14
PADDLE_HEIGHT = 90
PADDLE_SPEED  = 420
PADDLE_MARGIN = 50    # distance from edge

BALL_RADIUS   = 8
BALL_SPEED    = 520   # initial speed
BALL_MAX_SPEED = 850
BALL_SPEEDUP  = 18    # added to speed per paddle hit

WIN_SCORE     = 5

# AI difficulty settings (reaction delay in seconds + position error in pixels)
AI_EASY   = {"delay": 0.4, "error": 60}
AI_MEDIUM = {"delay": 0.18, "error": 25}
AI_HARD   = {"delay": 0.05, "error": 5}
