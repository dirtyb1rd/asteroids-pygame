# All colors as (R, G, B) tuples
BG          = (0x2A, 0x1F, 0x1D)   # background - dark warm brown
FG          = (0xE0, 0xDB, 0xB7)   # foreground - warm cream
DIM         = (0x57, 0x3D, 0x26)   # regular0 - dark brown, borders/inactive
RED         = (0xBE, 0x2D, 0x26)   # regular1 - muted red
GREEN       = (0x6B, 0xA1, 0x8A)   # regular2 - sage green
ORANGE      = (0xE9, 0x9D, 0x2A)   # regular3 - amber
BLUE        = (0x5A, 0x86, 0xAD)   # regular4 - steel blue
PURPLE      = (0xAC, 0x80, 0xA6)   # regular5 - dusty purple
CYAN        = (0x74, 0xA6, 0xAD)   # regular6 - teal
CREAM       = (0xE0, 0xDB, 0xB7)   # regular7 - warm white
HIGHLIGHT   = (0x9B, 0x6C, 0x4A)   # bright0 - golden brown, selection
BRIGHT_RED  = (0xE8, 0x46, 0x27)   # bright1 - vivid red
BRIGHT_GREEN= (0x95, 0xD8, 0xBA)   # bright2 - mint green
YELLOW      = (0xD0, 0xD1, 0x50)   # bright3 - lime yellow
LIGHT_BLUE  = (0xB8, 0xD3, 0xED)   # bright4 - pale blue
PINK        = (0xD1, 0x9E, 0xCB)   # bright5 - soft pink
LIGHT_CYAN  = (0x93, 0xCF, 0xD7)   # bright6 - light teal
WHITE       = (0xFF, 0xF9, 0xD5)   # bright7 - warm white (brightest)


def with_alpha(color: tuple, alpha: int) -> tuple:
    """Return (R, G, B, A) from a color tuple."""
    return (*color, alpha)
