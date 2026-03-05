"""
games/asteroids/game.py — AsteroidsGame

Modes:
  classic  — standard play, 3 lives, score multiplier x1
  survival — one life, difficulty ramps every 30 s, score = time survived
  hardcore — faster asteroids, faster spawns, no invulnerability, score x2
  zen      — infinite lives, slower spawns, no score pressure
"""
from __future__ import annotations

import pygame
import colors
import persistence
import ui
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, FONT_SIZE_LARGE, FONT_SIZE_MEDIUM, FONT_SIZE_SMALL, FONT_SIZE_TINY
from games.base import BaseGame
from logger import log_event

from .asteroid import Asteroid
from .asteroidfield import AsteroidField
from .player import Player
from .shot import Shot
from .constants import (
    PLAYER_LIVES,
    INVULNERABILITY_TIME,
    ASTEROID_SPAWN_RATE,
    HARDCORE_SPEED_MULT,
    HARDCORE_SPAWN_MULT,
    HARDCORE_SCORE_MULT,
    SURVIVAL_RAMP_INTERVAL,
    SURVIVAL_RAMP_SPAWN_MULT,
)

# State constants
_ST_PLAYING   = "PLAYING"
_ST_PAUSED    = "PAUSED"
_ST_GAME_OVER = "GAME_OVER"

_MODE_LABELS = {
    "classic":  "CLASSIC",
    "survival": "SURVIVAL",
    "hardcore": "HARDCORE",
    "zen":      "ZEN",
}


class AsteroidsGame(BaseGame):
    name    = "Asteroids"
    game_id = "asteroids"

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, mode: str = "classic"):
        super().__init__(screen, clock)
        self.mode = mode
        self._init_game()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_game(self) -> None:
        """Set up (or reset) all game state. Called on first run and on restart."""
        # --- Sprite groups ---
        self._updatable = pygame.sprite.Group()
        self._drawable  = pygame.sprite.Group()
        self._asteroids = pygame.sprite.Group()
        self._shots     = pygame.sprite.Group()

        # Wire containers before constructing any sprites
        Asteroid.containers     = (self._asteroids, self._updatable, self._drawable)
        AsteroidField.containers = self._updatable
        Shot.containers         = (self._shots,     self._updatable, self._drawable)
        Player.containers       = (self._updatable, self._drawable)

        # --- Mode-specific setup ---
        spawn_rate  = ASTEROID_SPAWN_RATE
        speed_mult  = 1.0
        lives       = PLAYER_LIVES

        if self.mode == "hardcore":
            speed_mult = HARDCORE_SPEED_MULT
            spawn_rate = HARDCORE_SPAWN_MULT
        elif self.mode == "survival":
            spawn_rate = ASTEROID_SPAWN_RATE   # starts normal, ramps over time
        elif self.mode == "zen":
            spawn_rate = ASTEROID_SPAWN_RATE * 1.5
            lives      = 999

        Asteroid.speed_mult = speed_mult

        # --- Spawn field & player ---
        self._field  = AsteroidField(spawn_rate=spawn_rate, speed_mult=speed_mult)
        self._player = Player(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)

        # --- Counters ---
        self._score           = 0
        self._lives           = lives
        self._survival_timer  = 0.0   # total elapsed for survival display
        self._difficulty_timer = 0.0  # time-since-last-ramp for survival

        # --- Effects ---
        self._particles    = ui.ParticleSystem()
        self._screen_shake = ui.ScreenShake()

        # --- Transition & state ---
        self._transition = ui.Transition(direction="in")
        self._state      = _ST_PLAYING

        # --- High score (loaded once, updated at game-over) ---
        self._high_score = persistence.get_score("asteroids", self.mode)
        self._new_record = False

    def _reset_player(self, grant_invuln: bool = True) -> None:
        """Move player back to centre and optionally restore invulnerability."""
        self._player.position = pygame.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self._player.velocity = pygame.Vector2(0, 0)
        if grant_invuln:
            self._player.invulnerable_timer = INVULNERABILITY_TIME
        else:
            self._player.invulnerable_timer = 0.0

    def _score_mult(self) -> int:
        return HARDCORE_SCORE_MULT if self.mode == "hardcore" else 1

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

            # ---- GAME OVER state ----
            if self._state == _ST_GAME_OVER:
                if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._init_game()
                elif key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
                continue

            # ---- PAUSED state ----
            if self._state == _ST_PAUSED:
                if key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._state = _ST_PLAYING
                elif key == pygame.K_q:
                    return False
                elif key == pygame.K_r:
                    self._init_game()
                    self._state = _ST_PLAYING
                continue

            # ---- PLAYING state ----
            if self._state == _ST_PLAYING:
                if key == pygame.K_ESCAPE:
                    self._state = _ST_PAUSED

        return True

    def update(self, dt: float) -> None:
        # Handle transition regardless of play state
        self._transition.update(dt)

        if self._state != _ST_PLAYING:
            return

        # Update screen-shake timer
        self._screen_shake.update(dt)

        # Survival: accumulate timers
        if self.mode == "survival":
            self._survival_timer  += dt
            self._difficulty_timer += dt
            if self._difficulty_timer >= SURVIVAL_RAMP_INTERVAL:
                self._difficulty_timer = 0.0
                self._field.spawn_rate = max(
                    0.1, self._field.spawn_rate * SURVIVAL_RAMP_SPAWN_MULT
                )

        # Update all sprites
        self._updatable.update(dt)

        # Particles
        self._particles.update(dt)

        # --- Collision: asteroids vs player ---
        if self._player.invulnerable_timer <= 0:
            for asteroid in list(self._asteroids):
                if asteroid.collides_with(self._player):
                    log_event("player_hit", mode=self.mode)
                    self._particles.emit(
                        self._player.position.x,
                        self._player.position.y,
                        count=20,
                        color=colors.BRIGHT_RED,
                        speed=180,
                        lifetime=0.9,
                        radius=4,
                    )
                    self._screen_shake.shake(intensity=10, duration=0.2)

                    if self.mode == "zen":
                        # No life loss — just reset position
                        self._reset_player(grant_invuln=True)
                    elif self.mode == "survival":
                        # One life, death = game over
                        self._trigger_game_over()
                    else:
                        self._lives -= 1
                        if self._lives <= 0:
                            self._trigger_game_over()
                        else:
                            grant = self.mode != "hardcore"
                            self._reset_player(grant_invuln=grant)
                    # Only process one hit per frame
                    break

        # --- Collision: asteroids vs shots ---
        for asteroid in list(self._asteroids):
            for shot in list(self._shots):
                if asteroid.collides_with(shot):
                    log_event("asteroid_shot", mode=self.mode)
                    self._particles.emit(
                        asteroid.position.x,
                        asteroid.position.y,
                        count=12,
                        color=colors.ORANGE,
                        speed=120,
                        lifetime=0.7,
                        radius=3,
                    )
                    points = asteroid.split()
                    shot.kill()
                    if points:
                        self._score += points * self._score_mult()
                    break   # asteroid is dead; no more shot checks for it

    def draw(self) -> None:
        # Compute shake offset and draw everything to a temp surface so we can
        # shift the entire scene by the shake amount without black borders.
        ox, oy = self._screen_shake.get_offset()

        self.screen.fill(colors.BG)

        # Draw game world (shifted by shake offset)
        if ox != 0 or oy != 0:
            world = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            world.fill(colors.BG)
            self._draw_world(world)
            self.screen.blit(world, (ox, oy))
        else:
            self._draw_world(self.screen)

        # HUD is always drawn without shake
        self._draw_hud(self.screen)

        # Overlays
        if self._state == _ST_PAUSED:
            self._draw_paused(self.screen)
        elif self._state == _ST_GAME_OVER:
            self._draw_game_over(self.screen)

        # Transition fade (drawn last so it sits on top of everything)
        self._transition.draw(self.screen)

        # CRT post-process
        ui.draw_crt(self.screen)

    # ------------------------------------------------------------------
    # Draw helpers
    # ------------------------------------------------------------------

    def _draw_world(self, surface: pygame.Surface) -> None:
        for obj in self._drawable:
            obj.draw(surface)
        self._particles.draw(surface)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        if self.mode == "survival":
            ui.draw_timer(surface, self._survival_timer)
            ui.draw_score(surface, self._score)
        else:
            ui.draw_score(surface, self._score)
            if self._lives < 999:
                ui.draw_lives(surface, self._lives)

        hi = max(self._high_score, self._score)
        ui.draw_high_score(surface, hi)

        # Mode badge — top-centre
        mode_label = _MODE_LABELS.get(self.mode, self.mode.upper())
        ui.draw_mode_label(surface, mode_label)

        ui.draw_fps(surface, self.clock.get_fps())

    def _draw_paused(self, surface: pygame.Surface) -> None:
        # Semi-transparent dark overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        cy = SCREEN_HEIGHT // 2
        ui.draw_text(surface, "PAUSED", FONT_SIZE_LARGE, SCREEN_WIDTH // 2, cy - 60,
                     color=colors.WHITE)
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

        mode_label = _MODE_LABELS.get(self.mode, self.mode.upper())
        ui.draw_text(surface, mode_label, FONT_SIZE_SMALL, cx, cy - 48,
                     color=colors.GREEN)

        if self.mode == "survival":
            total = int(self._survival_timer)
            mins  = total // 60
            secs  = total % 60
            score_str = f"TIME  {mins:02d}:{secs:02d}"
        else:
            score_str = f"SCORE  {self._score}"
        ui.draw_text(surface, score_str, FONT_SIZE_MEDIUM, cx, cy, color=colors.ORANGE)

        hi = self._high_score
        if self.mode == "survival":
            hi_total = int(hi)
            hi_mins  = hi_total // 60
            hi_secs  = hi_total % 60
            hi_str   = f"BEST  {hi_mins:02d}:{hi_secs:02d}"
        else:
            hi_str = f"BEST  {hi}"

        record_color = colors.YELLOW if self._new_record else colors.GREEN
        ui.draw_text(surface, hi_str, FONT_SIZE_SMALL, cx, cy + 52, color=record_color)

        if self._new_record:
            ui.draw_text(surface, "NEW RECORD!", FONT_SIZE_SMALL, cx, cy + 88,
                         color=colors.YELLOW)

        ui.draw_text(surface, "R / ENTER  restart       Q / ESC  menu", FONT_SIZE_SMALL,
                     cx, cy + 132, color=colors.GREEN)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _trigger_game_over(self) -> None:
        self._state = _ST_GAME_OVER
        log_event("game_over", mode=self.mode, score=self._score)

        # Persist: survival mode saves time, others save score
        if self.mode == "survival":
            value = self._survival_timer
        else:
            value = self._score

        self._new_record = persistence.set_score("asteroids", self.mode, value)
        # Refresh local high-score so the overlay shows the updated value
        self._high_score = persistence.get_score("asteroids", self.mode)

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        pass   # _init_game() already called in __init__

    def on_exit(self) -> None:
        # Clear class-level container refs so they don't leak to other games
        Asteroid.containers      = ()
        AsteroidField.containers = ()
        Shot.containers          = ()
        Player.containers        = ()
        # Reset speed_mult to default
        Asteroid.speed_mult = 1.0
