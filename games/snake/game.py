"""
games/snake/game.py — Snake game (classic / wrap / speedrun modes).
"""
from __future__ import annotations

import math
import random

import pygame

import colors
import persistence
import ui
from constants import FONT_SIZE_LARGE, FONT_SIZE_MEDIUM, FONT_SIZE_SMALL, FONT_SIZE_TINY
from games.base import BaseGame
from games.snake.constants import (
    BASE_TICK,
    CELL_SIZE,
    GRID_COLS,
    GRID_OFFSET_X,
    GRID_OFFSET_Y,
    GRID_ROWS,
    MIN_TICK,
    SPEED_RAMP,
    SPEEDRUN_GOAL,
    TICK_DECREASE,
)

# Grid area pixel dimensions (pre-computed for convenience)
GRID_W = GRID_COLS * CELL_SIZE
GRID_H = GRID_ROWS * CELL_SIZE

# Slightly lighter fill for the grid background
_GRID_BG_COLOR = (0x33, 0x28, 0x26)

# Starting snake position and length
_START_COL = GRID_COLS // 2
_START_ROW = GRID_ROWS // 2
_START_LEN  = 4


def _cell_rect(col: int, row: int) -> pygame.Rect:
    """Return the on-screen pixel rect for a grid cell (no inset)."""
    return pygame.Rect(
        GRID_OFFSET_X + col * CELL_SIZE,
        GRID_OFFSET_Y + row * CELL_SIZE,
        CELL_SIZE,
        CELL_SIZE,
    )


def _cell_center(col: int, row: int) -> tuple[int, int]:
    """Return the pixel center of a grid cell."""
    r = _cell_rect(col, row)
    return r.centerx, r.centery


class SnakeGame(BaseGame):
    """Snake game supporting classic, wrap, and speedrun modes."""

    name    = "Snake"
    game_id = "snake"

    # ------------------------------------------------------------------
    # Construction / reset
    # ------------------------------------------------------------------

    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        mode: str = "classic",
    ) -> None:
        super().__init__(screen, clock)
        self.mode = mode
        self._time_alive = 0.0   # total seconds since last reset (for sin pulsing)
        self._reset()

    def _reset(self) -> None:
        """Initialise (or re-initialise) all game state for a fresh game."""
        # Snake body: list of (col, row), head at index 0
        self.body: list[tuple[int, int]] = [
            (_START_COL - i, _START_ROW) for i in range(_START_LEN)
        ]
        self.direction: tuple[int, int] = (1, 0)   # moving right
        self.next_dir:  tuple[int, int] = (1, 0)

        self.growing: int = 0        # segments still to be added

        # Tick / timing
        self.tick_interval: float = BASE_TICK
        self.tick_timer:    float = 0.0

        # Scoring
        self.score:       int   = 0
        self.food_eaten:  int   = 0
        self._multiplier: float = 1.0   # classic/wrap only

        # Speedrun
        self.speedrun_timer:    float = 0.0
        self._speedrun_done:    bool  = False
        self._speedrun_finish:  float = 0.0   # completion time

        # State
        self.state:  str  = "PLAYING"
        self.paused: bool = False

        # Food
        self.food: tuple[int, int] = self._spawn_food()

        # High score (loaded once; persists across restarts within session)
        self.high_score: int = int(persistence.get_score("snake", self.mode))

        # UI helpers
        self.particles  = ui.ParticleSystem()
        self.transition = ui.Transition(direction="in")

        # Reset elapsed time for visual effects
        self._time_alive = 0.0

    # ------------------------------------------------------------------
    # Food spawning
    # ------------------------------------------------------------------

    def _spawn_food(self) -> tuple[int, int]:
        """Return a random empty cell. Falls back to any cell if grid is full."""
        occupied = set(self.body) if hasattr(self, "body") else set()
        empty = [
            (c, r)
            for c in range(GRID_COLS)
            for r in range(GRID_ROWS)
            if (c, r) not in occupied
        ]
        if not empty:
            # Grid completely full — shouldn't happen in practice
            return (random.randrange(GRID_COLS), random.randrange(GRID_ROWS))
        return random.choice(empty)

    # ------------------------------------------------------------------
    # BaseGame interface
    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> bool:
        for event in events:
            if event.type == pygame.QUIT:
                return False

            if event.type != pygame.KEYDOWN:
                continue

            key = event.key

            # ---- GAME_OVER state ----
            if self.state == "GAME_OVER":
                if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._reset()
                elif key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
                continue

            # ---- Q: quit to launcher (any non-game-over state) ----
            if key == pygame.K_q:
                return False

            # ---- ESC / SPACE: toggle pause ----
            if key in (pygame.K_ESCAPE, pygame.K_SPACE):
                self.paused = not self.paused
                continue

            # ---- Direction input (only meaningful while playing) ----
            if self.paused:
                if key == pygame.K_r:
                    self._reset()
                continue

            dx, dy = self.direction
            if key in (pygame.K_UP, pygame.K_w):
                if dy != 1:   # not moving down → allow up
                    self.next_dir = (0, -1)
            elif key in (pygame.K_DOWN, pygame.K_s):
                if dy != -1:
                    self.next_dir = (0, 1)
            elif key in (pygame.K_LEFT, pygame.K_a):
                if dx != 1:
                    self.next_dir = (-1, 0)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                if dx != -1:
                    self.next_dir = (1, 0)

        return True

    def update(self, dt: float) -> None:
        self.transition.update(dt)
        self._time_alive += dt
        self.particles.update(dt)

        if self.paused or self.state == "GAME_OVER":
            return

        # Speedrun timer
        if self.mode == "speedrun" and not self._speedrun_done:
            self.speedrun_timer += dt

        # Tick accumulation → snake step
        self.tick_timer += dt
        if self.tick_timer >= self.tick_interval:
            self.tick_timer -= self.tick_interval
            self._step()

    def draw(self) -> None:
        screen = self.screen

        # Background
        screen.fill(colors.BG)

        self._draw_grid()
        self._draw_food()
        self._draw_snake()
        self.particles.draw(screen)
        self._draw_hud()

        if self.state == "GAME_OVER":
            self._draw_overlay("GAME OVER", colors.BRIGHT_RED, show_restart=True)
        elif self.paused:
            self._draw_overlay("PAUSED", colors.YELLOW, show_restart=False)

        ui.draw_crt(screen)
        self.transition.draw(screen)

    # ------------------------------------------------------------------
    # Core step logic
    # ------------------------------------------------------------------

    def _step(self) -> None:
        # 1. Apply buffered direction (prevent 180° reversal)
        ndx, ndy = self.next_dir
        dx,  dy  = self.direction
        if (ndx, ndy) != (-dx, -dy):
            self.direction = (ndx, ndy)
        dx, dy = self.direction

        # 2. Compute new head position
        head_col, head_row = self.body[0]
        new_col = head_col + dx
        new_row = head_row + dy

        # 3. Boundary handling
        if self.mode == "classic":
            if not (0 <= new_col < GRID_COLS and 0 <= new_row < GRID_ROWS):
                self._game_over()
                return
        else:
            # wrap and speedrun both wrap around
            new_col %= GRID_COLS
            new_row %= GRID_ROWS

        new_head = (new_col, new_row)

        # 4. Check self-collision (exclude tail tip, which is about to move away)
        check_body = self.body[:-1] if self.growing == 0 else self.body
        if new_head in check_body:
            self._game_over()
            return

        # 5. Eat food?
        ate_food = (new_head == self.food)

        # 6. Prepend new head
        self.body.insert(0, new_head)

        # 7. Grow / shorten
        if self.growing > 0:
            self.growing -= 1
        else:
            self.body.pop()

        # 8. Post-eat logic
        if ate_food:
            self.growing   += 3
            self.food_eaten += 1

            # Score
            if self.mode != "speedrun":
                self._update_multiplier()
                self.score += int(10 * self._multiplier)
            # (speedrun score calculated at completion)

            # Speed ramp
            if self.food_eaten % SPEED_RAMP == 0:
                self.tick_interval = max(
                    MIN_TICK,
                    self.tick_interval - TICK_DECREASE,
                )

            # Spawn particles at food position
            cx, cy = _cell_center(*self.food)
            self.particles.emit(
                cx, cy,
                count=12,
                color=colors.BRIGHT_RED,
                speed=120,
                lifetime=0.6,
                radius=4,
            )

            # Speedrun completion check
            if self.mode == "speedrun" and self.food_eaten >= SPEEDRUN_GOAL:
                self._speedrun_done   = True
                self._speedrun_finish = self.speedrun_timer
                self.score = int(SPEEDRUN_GOAL / max(self.speedrun_timer, 0.001) * 1000)
                self._game_over()
                return

            self.food = self._spawn_food()

    def _update_multiplier(self) -> None:
        """Increase score multiplier every SPEED_RAMP food items."""
        if self.food_eaten > 0 and self.food_eaten % SPEED_RAMP == 0:
            self._multiplier *= 1.1

    def _game_over(self) -> None:
        self.state = "GAME_OVER"

        # Compute final speedrun score if not already done
        if self.mode == "speedrun" and not self._speedrun_done:
            # Did not complete — partial score based on food eaten
            if self.food_eaten > 0:
                self.score = int(
                    self.food_eaten / SPEEDRUN_GOAL
                    * (SPEEDRUN_GOAL / max(self.speedrun_timer, 0.001) * 1000)
                )

        # Persist high score
        if persistence.set_score("snake", self.mode, self.score):
            self.high_score = self.score

        # Explosion particles from snake head
        if self.body:
            cx, cy = _cell_center(*self.body[0])
            self.particles.emit(
                cx, cy,
                count=20,
                color=colors.BRIGHT_GREEN,
                speed=160,
                lifetime=1.0,
                radius=5,
            )

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_grid(self) -> None:
        screen = self.screen

        # Grid area background
        grid_surf = pygame.Surface((GRID_W, GRID_H))
        grid_surf.fill(_GRID_BG_COLOR)
        screen.blit(grid_surf, (GRID_OFFSET_X, GRID_OFFSET_Y))

        # Faint grid lines
        line_surf = pygame.Surface((GRID_W, GRID_H), pygame.SRCALPHA)
        line_col  = (*colors.DIM, 30)   # very dim lines
        for c in range(GRID_COLS + 1):
            x = c * CELL_SIZE
            pygame.draw.line(line_surf, line_col, (x, 0), (x, GRID_H))
        for r in range(GRID_ROWS + 1):
            y = r * CELL_SIZE
            pygame.draw.line(line_surf, line_col, (0, y), (GRID_W, y))
        screen.blit(line_surf, (GRID_OFFSET_X, GRID_OFFSET_Y))

        # Grid border
        border_rect = pygame.Rect(GRID_OFFSET_X - 1, GRID_OFFSET_Y - 1, GRID_W + 2, GRID_H + 2)
        pygame.draw.rect(screen, colors.DIM, border_rect, 1)

    def _draw_food(self) -> None:
        screen = self.screen
        cx, cy = _cell_center(*self.food)

        # Pulsing radius
        pulse = math.sin(self._time_alive * 4.0)
        max_r = CELL_SIZE // 2
        min_r = max_r - 3
        radius = int(min_r + (max_r - min_r) * (pulse * 0.5 + 0.5))

        # Glow: slightly larger, semi-transparent circle
        glow_surf = pygame.Surface((CELL_SIZE * 2, CELL_SIZE * 2), pygame.SRCALPHA)
        glow_r    = radius + 4
        r, g, b   = colors.BRIGHT_RED
        pygame.draw.circle(
            glow_surf, (r, g, b, 60),
            (CELL_SIZE, CELL_SIZE), glow_r,
        )
        screen.blit(glow_surf, (cx - CELL_SIZE, cy - CELL_SIZE))

        # Core circle
        pygame.draw.circle(screen, colors.BRIGHT_RED, (cx, cy), radius)

        # Small highlight dot
        hi_r = max(1, radius // 3)
        pygame.draw.circle(screen, colors.WHITE, (cx - hi_r, cy - hi_r), hi_r)

    def _draw_snake(self) -> None:
        screen  = self.screen
        n       = len(self.body)
        inset   = 2

        for i, (col, row) in enumerate(self.body):
            cell = _cell_rect(col, row)
            seg  = pygame.Rect(
                cell.x + inset,
                cell.y + inset,
                cell.width  - inset * 2,
                cell.height - inset * 2,
            )

            if i == 0:
                # Head
                color = colors.BRIGHT_GREEN
            else:
                # Fade from GREEN toward a darker shade at the tail
                t = i / max(n - 1, 1)   # 0 = near head, 1 = tail
                r = int(colors.GREEN[0] * (1 - t * 0.55))
                g = int(colors.GREEN[1] * (1 - t * 0.55))
                b = int(colors.GREEN[2] * (1 - t * 0.55))
                color = (r, g, b)

            pygame.draw.rect(screen, color, seg, border_radius=3)

            # Direction indicator on head
            if i == 0:
                dx, dy = self.direction
                eye_x = cell.centerx + dx * (CELL_SIZE // 4)
                eye_y = cell.centery + dy * (CELL_SIZE // 4)
                pygame.draw.circle(screen, colors.BG, (eye_x, eye_y), 2)

    def _draw_hud(self) -> None:
        screen = self.screen

        # Score (top-left via ui helper)
        ui.draw_score(screen, self.score)

        # Mode label (top-right)
        mode_label = self.mode.upper()
        ui.draw_mode_label(screen, mode_label)

        if self.mode == "speedrun":
            # Food progress
            progress = f"{self.food_eaten}/{SPEEDRUN_GOAL}"
            ui.draw_text(
                screen, progress,
                FONT_SIZE_SMALL,
                self.width - 80, 45,
                color=colors.BRIGHT_GREEN,
                align="right",
            )
            # Timer (top-center)
            ui.draw_timer(screen, self.speedrun_timer)
        else:
            # High score (top-right, below mode label)
            ui.draw_high_score(screen, self.high_score)

    def _draw_overlay(
        self,
        title: str,
        title_color: tuple,
        show_restart: bool,
    ) -> None:
        screen = self.screen

        # Semi-transparent dark rect over the grid
        overlay = pygame.Surface((GRID_W, GRID_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (GRID_OFFSET_X, GRID_OFFSET_Y))

        cx = GRID_OFFSET_X + GRID_W // 2
        cy = GRID_OFFSET_Y + GRID_H // 2

        # Title
        ui.draw_text(screen, title, FONT_SIZE_LARGE, cx, cy - 110, color=title_color)

        if self.state == "GAME_OVER":
            # Score
            ui.draw_text(
                screen, f"SCORE  {self.score}",
                FONT_SIZE_MEDIUM, cx, cy - 20,
                color=colors.ORANGE,
            )

            # High score
            hs_label = "BEST   " + str(self.high_score)
            new_record = self.score >= self.high_score and self.score > 0
            hs_color   = colors.YELLOW if new_record else colors.GREEN
            ui.draw_text(screen, hs_label, FONT_SIZE_SMALL, cx, cy + 30, color=hs_color)
            if new_record:
                ui.draw_text(
                    screen, "NEW RECORD!",
                    FONT_SIZE_TINY, cx, cy + 60,
                    color=colors.YELLOW,
                )

            # Speedrun completion time
            if self.mode == "speedrun" and self._speedrun_done:
                mins = int(self._speedrun_finish) // 60
                secs = int(self._speedrun_finish) % 60
                ms   = int((self._speedrun_finish % 1) * 100)
                time_str = f"TIME  {mins:02d}:{secs:02d}.{ms:02d}"
                ui.draw_text(
                    screen, time_str,
                    FONT_SIZE_SMALL, cx, cy + 80,
                    color=colors.LIGHT_CYAN,
                )

            if show_restart:
                ui.draw_text(
                    screen, "R / ENTER  restart       Q / ESC  menu",
                    FONT_SIZE_TINY, cx, cy + 115,
                    color=colors.GREEN,
                )
        else:
            # Paused
            ui.draw_text(
                screen, "SPACE / ESC  resume    R  restart    Q  menu",
                FONT_SIZE_TINY, cx, cy + 20,
                color=colors.GREEN,
            )
