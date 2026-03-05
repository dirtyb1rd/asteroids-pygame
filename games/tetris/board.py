import pygame
import colors
from .constants import BOARD_COLS, BOARD_ROWS, CELL_SIZE, BOARD_X, BOARD_Y, SCORE_TABLE, LEVEL_LINES


class Board:
    def __init__(self):
        # grid: BOARD_ROWS x BOARD_COLS, each cell is None or a color tuple
        self.grid: list[list] = [[None] * BOARD_COLS for _ in range(BOARD_ROWS)]
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.flash_rows: list[int] = []    # rows being cleared (for flash animation)
        self.flash_timer = 0.0
        self.FLASH_DURATION = 0.12

    def in_bounds(self, col, row) -> bool:
        return 0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS

    def is_empty(self, col, row) -> bool:
        return self.in_bounds(col, row) and self.grid[row][col] is None

    def place_piece(self, cells: list[tuple], color: tuple) -> int:
        """Lock a piece onto the grid. Returns number of lines cleared."""
        for col, row in cells:
            if self.in_bounds(col, row):
                self.grid[row][col] = color
        return self._clear_lines()

    def _clear_lines(self) -> int:
        full = [r for r in range(BOARD_ROWS) if all(self.grid[r][c] is not None for c in range(BOARD_COLS))]
        if not full:
            return 0
        self.flash_rows = full
        self.flash_timer = self.FLASH_DURATION
        for r in sorted(full, reverse=True):
            del self.grid[r]
            self.grid.insert(0, [None] * BOARD_COLS)
        count = len(full)
        self.lines_cleared += count
        pts = SCORE_TABLE.get(count, 0) * self.level
        self.score += pts
        self.level = self.lines_cleared // LEVEL_LINES + 1
        return count

    def update(self, dt):
        if self.flash_timer > 0:
            self.flash_timer = max(0, self.flash_timer - dt)

    def draw(self, screen):
        # Draw board background
        board_rect = pygame.Rect(BOARD_X - 2, BOARD_Y - 2, BOARD_COLS * CELL_SIZE + 4, BOARD_ROWS * CELL_SIZE + 4)
        pygame.draw.rect(screen, colors.DIM, board_rect, 2)

        # Draw cells
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                x = BOARD_X + col * CELL_SIZE
                y = BOARD_Y + row * CELL_SIZE
                cell_color = self.grid[row][col]
                if cell_color:
                    # flash cleared rows white
                    if row in self.flash_rows and self.flash_timer > 0:
                        draw_color = colors.WHITE
                    else:
                        draw_color = cell_color
                    r = pygame.Rect(x + 1, y + 1, CELL_SIZE - 2, CELL_SIZE - 2)
                    pygame.draw.rect(screen, draw_color, r)
                    # inner highlight
                    pygame.draw.rect(screen, colors.WHITE, r, 1)
                else:
                    # empty cell grid line
                    pygame.draw.rect(screen, colors.DIM, pygame.Rect(x, y, CELL_SIZE, CELL_SIZE), 1)
