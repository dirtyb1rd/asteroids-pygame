"""
games/breakout/game.py — BreakoutGame

Modes:
  classic — clear levels to advance; ball speeds up each level
  endless — new brick row drops from top each time a row is cleared;
            bricks reaching paddle = game over
"""
from __future__ import annotations

import math
import random

import pygame

import colors
import persistence
import ui
from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FONT_SIZE_LARGE,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
)
from games.base import BaseGame

from .constants import (
    PADDLE_WIDTH,
    PADDLE_HEIGHT,
    PADDLE_SPEED,
    PADDLE_Y,
    BALL_RADIUS,
    BALL_SPEED,
    BALL_MAX_SPEED,
    BALL_SPEEDUP,
    BRICK_COLS,
    BRICK_ROWS,
    BRICK_WIDTH,
    BRICK_HEIGHT,
    BRICK_PADDING,
    BRICK_TOP_Y,
    BRICK_START_X,
    PLAYER_LIVES,
)

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------
_ST_PLAYING   = "PLAYING"
_ST_PAUSED    = "PAUSED"
_ST_GAME_OVER = "GAME_OVER"

# Ball trail length
_TRAIL_LENGTH = 5

# Per-row brick definition: (hp, color, points)
# Row 0 = top row, row 6 = bottom row
_ROW_DEFS = [
    (2, colors.BRIGHT_RED,   30),   # row 0 — top
    (2, colors.ORANGE,       25),   # row 1
    (1, colors.YELLOW,       20),   # row 2
    (1, colors.BRIGHT_GREEN, 15),   # row 3
    (1, colors.CYAN,         12),   # row 4
    (1, colors.BLUE,         10),   # row 5
    (1, colors.PURPLE,        8),   # row 6 — bottom
]

# Speed increase when advancing to next level (classic)
_LEVEL_SPEED_BONUS = 20

# How far bricks shift down each time a new row is inserted (endless)
_ENDLESS_DROP_STEP = BRICK_HEIGHT + BRICK_PADDING


class BreakoutGame(BaseGame):
    name    = "Breakout"
    game_id = "breakout"

    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        mode: str = "classic",
    ):
        super().__init__(screen, clock)
        self.mode = mode
        self._init_game()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_game(self) -> None:
        """Reset all game state. Called on first run and restart."""
        # --- Paddle ---
        self._paddle = pygame.Rect(
            SCREEN_WIDTH // 2 - PADDLE_WIDTH // 2,
            PADDLE_Y,
            PADDLE_WIDTH,
            PADDLE_HEIGHT,
        )

        # --- Ball ---
        self._ball_x    = float(SCREEN_WIDTH // 2)
        self._ball_y    = float(PADDLE_Y - BALL_RADIUS - 2)
        self._ball_trail: list[tuple[float, float]] = []
        self._ball_speed = float(BALL_SPEED)
        self._launch_ball()

        # --- Ball on paddle (waiting to launch) ---
        self._on_paddle = True

        # --- Bricks ---
        self._bricks: list[dict] = []
        self._level = 1
        self._build_bricks()
        # Snapshot of current row Y values (used for endless row-clear detection)
        self._expected_row_ys: list[int] = sorted(set(b["rect"].y for b in self._bricks))

        # --- Endless-mode tracking ---
        # Count how many rows exist so we can detect when one is fully cleared
        self._endless_cleared_rows = 0

        # --- Scores & lives ---
        self._score = 0
        self._lives = PLAYER_LIVES

        # --- Effects ---
        self._particles    = ui.ParticleSystem()
        self._screen_shake = ui.ScreenShake()

        # --- Transition & state ---
        self._transition = ui.Transition(direction="in")
        self._state      = _ST_PLAYING

        # --- High score ---
        self._high_score = persistence.get_score("breakout", self.mode)
        self._new_record = False

    def _build_bricks(self) -> None:
        """Populate self._bricks from scratch using _ROW_DEFS."""
        self._bricks = []
        for row in range(BRICK_ROWS):
            hp, color, points = _ROW_DEFS[row % len(_ROW_DEFS)]
            for col in range(BRICK_COLS):
                x = BRICK_START_X + col * (BRICK_WIDTH + BRICK_PADDING)
                y = BRICK_TOP_Y   + row * (BRICK_HEIGHT + BRICK_PADDING)
                self._bricks.append({
                    "rect":      pygame.Rect(x, y, BRICK_WIDTH, BRICK_HEIGHT),
                    "color":     color,
                    "hp":        hp,
                    "max_hp":    hp,
                    "points":    points,
                })

    def _launch_ball(self) -> None:
        """Give the ball a random upward velocity."""
        angle = random.uniform(-math.pi / 4, math.pi / 4) - math.pi / 2
        self._ball_vx = math.cos(angle) * self._ball_speed
        self._ball_vy = math.sin(angle) * self._ball_speed
        # Ensure ball always travels upward on launch
        self._ball_vy = -abs(self._ball_vy)

    def _reset_ball_to_paddle(self) -> None:
        """Place ball on top of the paddle, waiting for space to launch."""
        self._ball_x     = float(self._paddle.centerx)
        self._ball_y     = float(PADDLE_Y - BALL_RADIUS - 2)
        self._ball_trail.clear()
        self._on_paddle  = True

    def _clamp_paddle(self) -> None:
        self._paddle.left  = max(0, self._paddle.left)
        self._paddle.right = min(SCREEN_WIDTH, self._paddle.right)

    # ------------------------------------------------------------------
    # Brick helpers
    # ------------------------------------------------------------------

    def _rows_occupied(self) -> set[int]:
        """Return a set of unique row indices that still have bricks."""
        rows: set[int] = set()
        for b in self._bricks:
            row_idx = (b["rect"].y - BRICK_TOP_Y) // (BRICK_HEIGHT + BRICK_PADDING)
            rows.add(row_idx)
        return rows

    def _count_bricks_in_row(self, row_y: int) -> int:
        """Count bricks whose rect.y equals row_y."""
        return sum(1 for b in self._bricks if b["rect"].y == row_y)

    def _get_all_row_ys(self) -> list[int]:
        """Sorted list of distinct brick Y positions."""
        ys: set[int] = set(b["rect"].y for b in self._bricks)
        return sorted(ys)

    def _insert_endless_row(self) -> None:
        """
        Push all existing bricks down by one row-height and
        insert a new row at the top (BRICK_TOP_Y).
        """
        # Shift existing bricks down
        for b in self._bricks:
            b["rect"].y += _ENDLESS_DROP_STEP

        # Check if any brick has reached/passed PADDLE_Y → game over
        for b in self._bricks:
            if b["rect"].bottom >= PADDLE_Y:
                self._trigger_game_over()
                return

        # Add new row at top
        row_idx = self._endless_cleared_rows % len(_ROW_DEFS)
        hp, color, points = _ROW_DEFS[row_idx]
        for col in range(BRICK_COLS):
            x = BRICK_START_X + col * (BRICK_WIDTH + BRICK_PADDING)
            y = BRICK_TOP_Y
            self._bricks.append({
                "rect":   pygame.Rect(x, y, BRICK_WIDTH, BRICK_HEIGHT),
                "color":  color,
                "hp":     hp,
                "max_hp": hp,
                "points": points,
            })

    # ------------------------------------------------------------------
    # BaseGame interface
    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> bool:
        for event in events:
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                key = event.key

                # ---- GAME OVER ----
                if self._state == _ST_GAME_OVER:
                    if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._init_game()
                    elif key in (pygame.K_ESCAPE, pygame.K_q):
                        return False
                    continue

                # ---- PAUSED ----
                if self._state == _ST_PAUSED:
                    if key in (pygame.K_ESCAPE, pygame.K_SPACE,
                               pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._state = _ST_PLAYING
                    elif key == pygame.K_r:
                        self._init_game()
                    elif key == pygame.K_q:
                        return False
                    continue

                # ---- PLAYING ----
                if self._state == _ST_PLAYING:
                    if key == pygame.K_ESCAPE:
                        self._state = _ST_PAUSED
                    elif key == pygame.K_SPACE and not self._on_paddle:
                        self._state = _ST_PAUSED
                    elif key == pygame.K_SPACE and self._on_paddle:
                        self._on_paddle = False
                        self._launch_ball()

        return True

    def update(self, dt: float) -> None:
        self._transition.update(dt)

        if self._state != _ST_PLAYING:
            return

        self._screen_shake.update(dt)
        self._particles.update(dt)

        # --- Paddle movement ---
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self._paddle.x -= int(PADDLE_SPEED * dt)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self._paddle.x += int(PADDLE_SPEED * dt)
        self._clamp_paddle()

        # If ball is on paddle, track paddle center
        if self._on_paddle:
            self._ball_x = float(self._paddle.centerx)
            self._ball_y = float(PADDLE_Y - BALL_RADIUS - 2)
            return

        # --- Move ball ---
        self._ball_trail.append((self._ball_x, self._ball_y))
        if len(self._ball_trail) > _TRAIL_LENGTH:
            self._ball_trail.pop(0)

        self._ball_x += self._ball_vx * dt
        self._ball_y += self._ball_vy * dt

        # --- Wall bounces ---
        # Left wall
        if self._ball_x - BALL_RADIUS <= 0:
            self._ball_x  = float(BALL_RADIUS)
            self._ball_vx = abs(self._ball_vx)
        # Right wall
        elif self._ball_x + BALL_RADIUS >= SCREEN_WIDTH:
            self._ball_x  = float(SCREEN_WIDTH - BALL_RADIUS)
            self._ball_vx = -abs(self._ball_vx)
        # Ceiling
        if self._ball_y - BALL_RADIUS <= 0:
            self._ball_y  = float(BALL_RADIUS)
            self._ball_vy = abs(self._ball_vy)

        # --- Paddle collision ---
        ball_rect = pygame.Rect(
            int(self._ball_x) - BALL_RADIUS,
            int(self._ball_y) - BALL_RADIUS,
            BALL_RADIUS * 2,
            BALL_RADIUS * 2,
        )
        if self._ball_vy > 0 and ball_rect.colliderect(self._paddle):
            self._handle_paddle_hit()

        # --- Ball out of bottom ---
        if self._ball_y - BALL_RADIUS > SCREEN_HEIGHT:
            self._lives -= 1
            self._particles.emit(
                self._ball_x, SCREEN_HEIGHT - 10,
                count=12, color=colors.RED,
                speed=140, lifetime=0.7, radius=3,
            )
            self._screen_shake.shake(intensity=6, duration=0.15)
            if self._lives <= 0:
                self._trigger_game_over()
            else:
                self._reset_ball_to_paddle()
            return

        # --- Brick collisions ---
        self._check_brick_collisions()

        # --- Classic: level complete check ---
        if self.mode == "classic" and not self._bricks:
            self._next_level()

        # --- Endless: check if a full row was cleared ---
        if self.mode == "endless":
            self._check_endless_row_clear()

    def _handle_paddle_hit(self) -> None:
        """Bounce ball off paddle, adjusting angle by hit position."""
        relative = (self._ball_x - self._paddle.centerx) / (PADDLE_WIDTH / 2)
        relative = max(-1.0, min(1.0, relative))
        # Angle ranges from -75° to +75° depending on hit position
        bounce_angle = relative * math.radians(75)
        self._ball_vy = -abs(self._ball_vy)  # always reflect upward
        self._ball_vx = self._ball_speed * math.sin(bounce_angle)
        self._ball_y  = float(self._paddle.top - BALL_RADIUS - 1)

        self._particles.emit(
            self._ball_x, self._ball_y,
            count=6, color=colors.CREAM, speed=90, lifetime=0.3, radius=2,
        )

    def _check_brick_collisions(self) -> None:
        """Test ball against all bricks; handle HP, scoring, particle emission."""
        bx = self._ball_x
        by = self._ball_y
        r  = BALL_RADIUS

        ball_rect = pygame.Rect(
            int(bx) - r, int(by) - r, r * 2, r * 2
        )

        hit_brick = None
        hit_overlap = 0

        for brick in self._bricks:
            if ball_rect.colliderect(brick["rect"]):
                # Prefer the brick with maximum overlap area
                overlap = ball_rect.clip(brick["rect"])
                area = overlap.width * overlap.height
                if area > hit_overlap:
                    hit_overlap = area
                    hit_brick = brick

        if hit_brick is None:
            return

        br = hit_brick["rect"]

        # Determine collision axis by comparing overlap dimensions
        overlap = ball_rect.clip(br)
        if overlap.width < overlap.height:
            # Hit left or right side of brick → reflect vx
            if bx < br.centerx:
                self._ball_x = float(br.left  - r - 1)
            else:
                self._ball_x = float(br.right + r + 1)
            self._ball_vx = -self._ball_vx
        else:
            # Hit top or bottom of brick → reflect vy
            if by < br.centery:
                self._ball_y = float(br.top    - r - 1)
            else:
                self._ball_y = float(br.bottom + r + 1)
            self._ball_vy = -self._ball_vy

        # Speed up slightly per hit
        self._ball_speed = min(self._ball_speed + BALL_SPEEDUP, BALL_MAX_SPEED)
        mag = math.hypot(self._ball_vx, self._ball_vy)
        if mag > 0:
            scale = self._ball_speed / mag
            self._ball_vx *= scale
            self._ball_vy *= scale

        # Damage brick
        hit_brick["hp"] -= 1
        if hit_brick["hp"] <= 0:
            self._bricks.remove(hit_brick)
            self._score += hit_brick["points"]
            self._particles.emit(
                br.centerx, br.centery,
                count=10, color=hit_brick["color"],
                speed=130, lifetime=0.55, radius=4,
            )
            self._screen_shake.shake(intensity=3, duration=0.07)
        else:
            # Still alive — lighter particle burst
            self._particles.emit(
                br.centerx, br.centery,
                count=4, color=colors.DIM,
                speed=70, lifetime=0.3, radius=2,
            )

    def _check_endless_row_clear(self) -> None:
        """In endless mode, insert a new top row whenever a full row disappears."""
        if self._state != _ST_PLAYING:
            return

        # Collect remaining brick Y values
        remaining_ys = set(b["rect"].y for b in self._bricks)

        # Compare current brick Ys against the expected snapshot to find
        # which rows were fully cleared since the last check.
        expected = set(self._expected_row_ys)
        cleared_ys = expected - remaining_ys

        for _ in cleared_ys:
            self._endless_cleared_rows += 1
            self._insert_endless_row()
            # Update expected set after insertion
            self._expected_row_ys = sorted(set(b["rect"].y for b in self._bricks))

    def _next_level(self) -> None:
        """Advance to the next level (classic mode)."""
        self._level += 1
        # Speed up ball
        self._ball_speed = min(self._ball_speed + _LEVEL_SPEED_BONUS, BALL_MAX_SPEED)
        # Rebuild bricks
        self._build_bricks()
        # Reset ball to paddle
        self._reset_ball_to_paddle()

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self) -> None:
        ox, oy = self._screen_shake.get_offset()
        self.screen.fill(colors.BG)

        if ox != 0 or oy != 0:
            world = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            world.fill(colors.BG)
            self._draw_world(world)
            self.screen.blit(world, (ox, oy))
        else:
            self._draw_world(self.screen)

        self._draw_hud(self.screen)

        if self._state == _ST_PAUSED:
            self._draw_paused(self.screen)
        elif self._state == _ST_GAME_OVER:
            self._draw_game_over(self.screen)

        self._transition.draw(self.screen)
        ui.draw_crt(self.screen)

    def _draw_world(self, surface: pygame.Surface) -> None:
        # Draw bricks
        for brick in self._bricks:
            self._draw_brick(surface, brick)

        # Ball trail
        for i, (tx, ty) in enumerate(self._ball_trail):
            alpha_frac = (i + 1) / (len(self._ball_trail) + 1)
            r = max(1, int(BALL_RADIUS * alpha_frac * 0.65))
            alpha = int(160 * alpha_frac * 0.5)
            trail_surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            cr, cg, cb = colors.YELLOW
            pygame.draw.circle(
                trail_surf, (cr, cg, cb, alpha),
                (r + 1, r + 1), r,
            )
            surface.blit(trail_surf, (int(tx) - r - 1, int(ty) - r - 1))

        # Ball
        pygame.draw.circle(
            surface, colors.YELLOW,
            (int(self._ball_x), int(self._ball_y)),
            BALL_RADIUS,
        )

        # Paddle
        pygame.draw.rect(surface, colors.CREAM, self._paddle, border_radius=4)

        # Particles
        self._particles.draw(surface)

    def _draw_brick(self, surface: pygame.Surface, brick: dict) -> None:
        rect     = brick["rect"]
        color    = brick["color"]
        hp       = brick["hp"]
        max_hp   = brick["max_hp"]

        # Draw main brick
        pygame.draw.rect(surface, color, rect, border_radius=3)

        # If brick was HP=2 and is now HP=1, draw cracked overlay
        if max_hp == 2 and hp == 1:
            # Semi-transparent DIM overlay at ~50% alpha
            overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            r2, g2, b2 = colors.DIM
            overlay.fill((r2, g2, b2, 128))
            surface.blit(overlay, rect.topleft)

            # Draw two hairline diagonal cracks in DIM
            crack_color = colors.DIM
            pygame.draw.line(
                surface, crack_color,
                (rect.left + rect.width  // 4, rect.top),
                (rect.left + rect.width  // 2, rect.bottom),
                1,
            )
            pygame.draw.line(
                surface, crack_color,
                (rect.left + rect.width  * 3 // 4, rect.top),
                (rect.left + rect.width  // 2, rect.bottom),
                1,
            )

        # Subtle border
        pygame.draw.rect(surface, colors.BG, rect, width=1, border_radius=3)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        # Score — top left
        ui.draw_score(surface, self._score)

        # High score — top right
        best = int(max(self._score, self._high_score))
        ui.draw_high_score(surface, best)

        # Level — top center
        ui.draw_text(
            surface, f"LEVEL  {self._level}",
            FONT_SIZE_TINY, SCREEN_WIDTH // 2, 10,
            color=colors.GREEN,
        )

        # Lives — small circles at bottom left
        self._draw_lives_circles(surface)

        # Mode badge
        mode_label = "CLASSIC" if self.mode == "classic" else "ENDLESS"
        ui.draw_mode_label(surface, mode_label)

        ui.draw_fps(surface, self.clock.get_fps())

    def _draw_lives_circles(self, surface: pygame.Surface) -> None:
        radius = 6
        spacing = 18
        x_start = 80
        y = SCREEN_HEIGHT - 28
        for i in range(self._lives):
            cx = x_start + i * spacing
            pygame.draw.circle(surface, colors.ORANGE, (cx, y), radius)

    def _draw_paused(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        cy = SCREEN_HEIGHT // 2
        ui.draw_text(surface, "PAUSED", FONT_SIZE_LARGE,
                     SCREEN_WIDTH // 2, cy - 60, color=colors.WHITE)
        ui.draw_text(surface, "SPACE / ESC  resume", FONT_SIZE_SMALL,
                     SCREEN_WIDTH // 2, cy + 20, color=colors.GREEN)
        ui.draw_text(surface, "R  restart       Q  menu", FONT_SIZE_SMALL,
                     SCREEN_WIDTH // 2, cy + 60, color=colors.GREEN)

    def _draw_game_over(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        ui.draw_text(surface, "GAME OVER", FONT_SIZE_LARGE, cx, cy - 120,
                     color=colors.BRIGHT_RED)

        mode_label = "CLASSIC" if self.mode == "classic" else "ENDLESS"
        ui.draw_text(surface, mode_label, FONT_SIZE_SMALL, cx, cy - 48,
                     color=colors.GREEN)

        ui.draw_text(surface, f"SCORE  {self._score}", FONT_SIZE_MEDIUM,
                     cx, cy, color=colors.ORANGE)

        best = max(self._score, self._high_score)
        record_color = colors.YELLOW if self._new_record else colors.FG
        ui.draw_text(surface, f"BEST  {best}", FONT_SIZE_SMALL,
                     cx, cy + 52, color=record_color)

        if self._new_record:
            ui.draw_text(surface, "NEW RECORD!", FONT_SIZE_SMALL,
                         cx, cy + 88, color=colors.YELLOW)

        ui.draw_text(surface, "R / ENTER  restart       Q / ESC  menu", FONT_SIZE_SMALL,
                     cx, cy + 132, color=colors.GREEN)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _trigger_game_over(self) -> None:
        self._state  = _ST_GAME_OVER
        self._new_record = persistence.set_score("breakout", self.mode, self._score)
        self._high_score = persistence.get_score("breakout", self.mode)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        pass  # _init_game() called in __init__

    def on_exit(self) -> None:
        pass
