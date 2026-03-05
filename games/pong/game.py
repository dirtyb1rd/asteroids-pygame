"""
games/pong/game.py — PongGame

Modes:
  vs_player — two human players (W/S vs Up/Down)
  easy      — right paddle is AI (low skill)
  medium    — right paddle is AI (medium skill)
  hard      — right paddle is AI (high skill)
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
    PADDLE_MARGIN,
    BALL_RADIUS,
    BALL_SPEED,
    BALL_MAX_SPEED,
    BALL_SPEEDUP,
    WIN_SCORE,
    AI_EASY,
    AI_MEDIUM,
    AI_HARD,
)

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------
_ST_PLAYING   = "PLAYING"
_ST_PAUSED    = "PAUSED"
_ST_GAME_OVER = "GAME_OVER"

# Number of trail positions to keep for the ball
_TRAIL_LENGTH = 5


class PongGame(BaseGame):
    name    = "Pong"
    game_id = "pong"

    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        mode: str = "medium",
    ):
        super().__init__(screen, clock)
        self.mode = mode
        self._ai_cfg = self._resolve_ai_cfg()
        self._init_game()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_ai_cfg(self) -> dict | None:
        """Return AI config dict for CPU modes, or None for vs_player."""
        return {
            "easy":   AI_EASY,
            "medium": AI_MEDIUM,
            "hard":   AI_HARD,
        }.get(self.mode)

    def _init_game(self) -> None:
        """Reset all game state. Called on first run and on restart."""
        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        # --- Paddle rects ---
        self._left_paddle  = pygame.Rect(
            PADDLE_MARGIN,
            cy - PADDLE_HEIGHT // 2,
            PADDLE_WIDTH,
            PADDLE_HEIGHT,
        )
        self._right_paddle = pygame.Rect(
            SCREEN_WIDTH - PADDLE_MARGIN - PADDLE_WIDTH,
            cy - PADDLE_HEIGHT // 2,
            PADDLE_WIDTH,
            PADDLE_HEIGHT,
        )

        # --- Ball ---
        self._ball_x = float(cx)
        self._ball_y = float(cy)
        self._ball_trail: list[tuple[float, float]] = []
        self._launch_ball(direction=1)

        # --- Scores ---
        self._score_left  = 0
        self._score_right = 0
        self._rally        = 0
        self._best_rally   = 0

        # --- AI state ---
        self._ai_target_y  = float(cy)
        self._ai_delay_acc = 0.0   # accumulated time for delay

        # --- Serve pause: brief freeze after scoring ---
        self._serve_timer = 0.0

        # --- Effects ---
        self._particles    = ui.ParticleSystem()
        self._screen_shake = ui.ScreenShake()

        # --- Transition & state ---
        self._transition = ui.Transition(direction="in")
        self._state      = _ST_PLAYING

        # --- High score (best rally for CPU modes) ---
        self._high_score = persistence.get_score("pong", "vs_cpu")
        self._new_record = False

        # --- Winner ---
        self._winner: str = ""

    def _launch_ball(self, direction: int = 1) -> None:
        """Set ball velocity. direction: +1 = toward right, -1 = toward left."""
        angle = random.uniform(-math.pi / 4, math.pi / 4)
        speed = float(BALL_SPEED)
        self._ball_vx = math.cos(angle) * speed * direction
        self._ball_vy = math.sin(angle) * speed
        self._ball_speed = speed

    def _reset_ball(self, scorer: str) -> None:
        """Emit particles, pause briefly, then relaunch toward the scorer's opponent."""
        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2
        self._particles.emit(
            self._ball_x, self._ball_y,
            count=14, color=colors.YELLOW,
            speed=160, lifetime=0.6, radius=4,
        )
        self._screen_shake.shake(intensity=5, duration=0.12)
        self._ball_x = float(cx)
        self._ball_y = float(cy)
        self._ball_trail.clear()
        self._serve_timer = 0.8
        # Launch toward the player who just conceded (to make it their serve)
        direction = -1 if scorer == "left" else 1
        self._launch_ball(direction=direction)
        self._rally = 0

    def _clamp_paddle(self, rect: pygame.Rect) -> None:
        """Keep paddle within vertical screen bounds."""
        rect.top    = max(0, rect.top)
        rect.bottom = min(SCREEN_HEIGHT, rect.bottom)

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

            # ---- GAME OVER ----
            if self._state == _ST_GAME_OVER:
                if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._init_game()
                elif key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
                continue

            # ---- PAUSED ----
            if self._state == _ST_PAUSED:
                if key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._state = _ST_PLAYING
                elif key == pygame.K_r:
                    self._init_game()
                elif key == pygame.K_q:
                    return False
                continue

            # ---- PLAYING ----
            if self._state == _ST_PLAYING:
                if key in (pygame.K_ESCAPE, pygame.K_SPACE):
                    self._state = _ST_PAUSED

        return True

    def update(self, dt: float) -> None:
        self._transition.update(dt)

        if self._state != _ST_PLAYING:
            return

        self._screen_shake.update(dt)
        self._particles.update(dt)

        # --- Serve freeze ---
        if self._serve_timer > 0:
            self._serve_timer -= dt
            return

        # --- Left paddle input ---
        # Left player: W/S or Up/Down arrows
        # vs_player right player uses I/K to avoid conflict
        keys = pygame.key.get_pressed()
        left_up   = keys[pygame.K_w] or keys[pygame.K_UP]
        left_down = keys[pygame.K_s] or keys[pygame.K_DOWN]
        if left_up:
            self._left_paddle.y -= int(PADDLE_SPEED * dt)
        if left_down:
            self._left_paddle.y += int(PADDLE_SPEED * dt)
        self._clamp_paddle(self._left_paddle)

        # --- Right paddle ---
        if self.mode == "vs_player":
            if keys[pygame.K_i]:
                self._right_paddle.y -= int(PADDLE_SPEED * dt)
            if keys[pygame.K_k]:
                self._right_paddle.y += int(PADDLE_SPEED * dt)
        else:
            self._update_ai(dt)
        self._clamp_paddle(self._right_paddle)

        # --- Move ball ---
        self._ball_trail.append((self._ball_x, self._ball_y))
        if len(self._ball_trail) > _TRAIL_LENGTH:
            self._ball_trail.pop(0)

        self._ball_x += self._ball_vx * dt
        self._ball_y += self._ball_vy * dt

        # --- Wall bounce (top / bottom) ---
        if self._ball_y - BALL_RADIUS <= 0:
            self._ball_y = float(BALL_RADIUS)
            self._ball_vy = abs(self._ball_vy)
            self._particles.emit(
                self._ball_x, self._ball_y,
                count=6, color=colors.DIM, speed=80, lifetime=0.3, radius=2,
            )
        elif self._ball_y + BALL_RADIUS >= SCREEN_HEIGHT:
            self._ball_y = float(SCREEN_HEIGHT - BALL_RADIUS)
            self._ball_vy = -abs(self._ball_vy)
            self._particles.emit(
                self._ball_x, self._ball_y,
                count=6, color=colors.DIM, speed=80, lifetime=0.3, radius=2,
            )

        # --- Paddle collisions ---
        ball_rect = pygame.Rect(
            int(self._ball_x) - BALL_RADIUS,
            int(self._ball_y) - BALL_RADIUS,
            BALL_RADIUS * 2,
            BALL_RADIUS * 2,
        )

        if self._ball_vx < 0 and ball_rect.colliderect(self._left_paddle):
            self._handle_paddle_hit(self._left_paddle, side="left")

        elif self._ball_vx > 0 and ball_rect.colliderect(self._right_paddle):
            self._handle_paddle_hit(self._right_paddle, side="right")

        # --- Scoring ---
        if self._ball_x - BALL_RADIUS <= 0:
            # Right player scores
            self._score_right += 1
            self._reset_ball(scorer="right")
            if self._score_right >= WIN_SCORE:
                self._trigger_game_over(winner="right")

        elif self._ball_x + BALL_RADIUS >= SCREEN_WIDTH:
            # Left player scores
            self._score_left += 1
            self._reset_ball(scorer="left")
            if self._score_left >= WIN_SCORE:
                self._trigger_game_over(winner="left")

    def _handle_paddle_hit(self, paddle: pygame.Rect, side: str) -> None:
        """Reflect the ball off a paddle and apply angle/speed changes."""
        # How far from center (-0.5 … +0.5)
        relative = (self._ball_y - paddle.centery) / (PADDLE_HEIGHT / 2)
        relative = max(-1.0, min(1.0, relative))

        # Angle: min 15° near center, max 60° at edge — prevents flat back-and-forth
        _MIN_ANGLE = math.radians(15)
        _MAX_ANGLE = math.radians(60)
        bounce_angle = relative * _MAX_ANGLE
        if bounce_angle >= 0:
            bounce_angle = max(bounce_angle, _MIN_ANGLE)
        else:
            bounce_angle = min(bounce_angle, -_MIN_ANGLE)

        # Increase speed, cap at max
        self._ball_speed = min(self._ball_speed + BALL_SPEEDUP, BALL_MAX_SPEED)

        if side == "left":
            self._ball_vx =  self._ball_speed * math.cos(bounce_angle)
            self._ball_x  = self._left_paddle.right + BALL_RADIUS + 1
        else:
            self._ball_vx = -self._ball_speed * math.cos(bounce_angle)
            self._ball_x  = self._right_paddle.left - BALL_RADIUS - 1

        self._ball_vy = self._ball_speed * math.sin(bounce_angle)

        self._rally += 1
        if self._rally > self._best_rally:
            self._best_rally = self._rally

        self._particles.emit(
            self._ball_x, self._ball_y,
            count=8, color=colors.CREAM, speed=100, lifetime=0.35, radius=3,
        )

    def _update_ai(self, dt: float) -> None:
        """Move right paddle AI toward ball with delay and positional error."""
        cfg = self._ai_cfg
        delay = cfg["delay"]
        error = cfg["error"]

        self._ai_delay_acc += dt
        if self._ai_delay_acc >= delay:
            self._ai_delay_acc = 0.0
            noise = random.gauss(0, error)
            self._ai_target_y = self._ball_y + noise

        # Move paddle center toward target
        center = float(self._right_paddle.centery)
        diff   = self._ai_target_y - center
        move   = PADDLE_SPEED * dt

        if abs(diff) <= move:
            self._right_paddle.centery = int(self._ai_target_y)
        elif diff > 0:
            self._right_paddle.y += int(move)
        else:
            self._right_paddle.y -= int(move)

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
        # Center dashed line
        dash_w = 6
        dash_h = 14
        gap    = 20
        cx = SCREEN_WIDTH // 2
        y  = 0
        while y < SCREEN_HEIGHT:
            pygame.draw.rect(
                surface, colors.DIM,
                pygame.Rect(cx - dash_w // 2, y, dash_w, dash_h),
            )
            y += dash_h + gap

        # Ball trail
        for i, (tx, ty) in enumerate(self._ball_trail):
            alpha_frac = (i + 1) / (len(self._ball_trail) + 1)
            r = max(1, int(BALL_RADIUS * alpha_frac * 0.7))
            alpha = int(180 * alpha_frac * 0.5)
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

        # Paddles (rounded rects)
        pygame.draw.rect(surface, colors.CREAM, self._left_paddle,  border_radius=4)
        pygame.draw.rect(surface, colors.CREAM, self._right_paddle, border_radius=4)

        # Particles
        self._particles.draw(surface)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        cx = SCREEN_WIDTH // 2

        # Scores — large, left/right of center
        score_offset = 120
        ui.draw_text(
            surface, str(self._score_left),
            FONT_SIZE_LARGE, cx - score_offset, 16,
            color=colors.ORANGE, align="right",
        )
        ui.draw_text(
            surface, str(self._score_right),
            FONT_SIZE_LARGE, cx + score_offset, 16,
            color=colors.LIGHT_BLUE, align="left",
        )

        # VS in the middle
        ui.draw_text(surface, "VS", FONT_SIZE_SMALL, cx, 30, color=colors.GREEN)

        # Rally counter — subtle, below scores
        if self._rally > 0:
            ui.draw_text(
                surface, f"rally  {self._rally}",
                FONT_SIZE_TINY, cx, 96,
                color=colors.GREEN,
            )

        # Best rally / high score (CPU modes only)
        if self.mode != "vs_player":
            best = max(self._best_rally, self._high_score)
            ui.draw_text(
                surface, f"best  {int(best)}",
                FONT_SIZE_TINY, SCREEN_WIDTH - 80, 25,
                color=colors.GREEN, align="right",
            )

        # Mode label
        mode_label = {
            "vs_player": "VS PLAYER",
            "easy":      "VS CPU  EASY",
            "medium":    "VS CPU  MEDIUM",
            "hard":      "VS CPU  HARD",
        }.get(self.mode, self.mode.upper())
        ui.draw_mode_label(surface, mode_label)

        ui.draw_fps(surface, self.clock.get_fps())

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

        # Winner announcement
        if self._winner == "left":
            winner_text  = "LEFT WINS"
            winner_color = colors.ORANGE
        else:
            winner_text  = "RIGHT WINS"
            winner_color = colors.LIGHT_BLUE

        ui.draw_text(surface, winner_text, FONT_SIZE_LARGE, cx, cy - 120,
                     color=winner_color)

        # Final score
        score_str = f"{self._score_left}  —  {self._score_right}"
        ui.draw_text(surface, score_str, FONT_SIZE_MEDIUM, cx, cy - 20,
                     color=colors.CREAM)

        # Best rally (CPU modes)
        if self.mode != "vs_player":
            best = max(self._best_rally, self._high_score)
            record_color = colors.YELLOW if self._new_record else colors.FG
            ui.draw_text(
                surface, f"best rally  {int(best)}",
                FONT_SIZE_SMALL, cx, cy + 44,
                color=record_color,
            )
            if self._new_record:
                ui.draw_text(surface, "NEW RECORD!", FONT_SIZE_SMALL, cx, cy + 80,
                             color=colors.YELLOW)

        ui.draw_text(surface, "R / ENTER  play again       Q / ESC  menu", FONT_SIZE_SMALL,
                     cx, cy + 128, color=colors.GREEN)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _trigger_game_over(self, winner: str) -> None:
        self._state  = _ST_GAME_OVER
        self._winner = winner

        # Persist best rally for CPU modes
        if self.mode != "vs_player":
            self._new_record = persistence.set_score(
                "pong", "vs_cpu", self._best_rally
            )
            self._high_score = persistence.get_score("pong", "vs_cpu")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        pass  # _init_game() called in __init__

    def on_exit(self) -> None:
        pass
