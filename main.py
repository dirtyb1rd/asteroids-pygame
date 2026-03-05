"""
main.py — Retro Arcade Launcher

Launcher menu with animated star background, game/mode selection,
and persistent high scores. All games share the same window and
colour theme.

Controls in launcher:
  Up / Down   — navigate
  Enter       — select / confirm
  Escape      — back / quit
  F3          — toggle FPS counter
  F4          — toggle CRT effects
"""
from __future__ import annotations

import math
import random
import sys

import pygame

import colors
import persistence
import ui
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, FONT_SIZE_LARGE, FONT_SIZE_MEDIUM, FONT_SIZE_SMALL, FONT_SIZE_TINY

# ---------------------------------------------------------------------------
# Game registry
# ---------------------------------------------------------------------------
# Each entry: (label, game_id, module_path, class_name, modes)
# modes: list of (display_label, mode_key)
_GAME_REGISTRY = [
    {
        "label":   "ASTEROIDS",
        "game_id": "asteroids",
        "cls":     None,   # lazy import
        "module":  "games.asteroids",
        "class":   "AsteroidsGame",
        "modes": [
            ("CLASSIC",  "classic"),
            ("SURVIVAL", "survival"),
            ("HARDCORE", "hardcore"),
            ("ZEN",      "zen"),
        ],
        "desc": "Destroy asteroids. Don't get hit.",
    },
    {
        "label":   "SNAKE",
        "game_id": "snake",
        "cls":     None,
        "module":  "games.snake",
        "class":   "SnakeGame",
        "modes": [
            ("CLASSIC",   "classic"),
            ("WRAP",      "wrap"),
            ("SPEED RUN", "speedrun"),
        ],
        "desc": "Eat. Grow. Don't bite yourself.",
    },
    {
        "label":   "TETRIS",
        "game_id": "tetris",
        "cls":     None,
        "module":  "games.tetris",
        "class":   "TetrisGame",
        "modes": [
            ("MARATHON", "marathon"),
            ("SPRINT",   "sprint"),
            ("ULTRA",    "ultra"),
        ],
        "desc": "Clear lines. Beat the clock.",
    },
    {
        "label":   "PONG",
        "game_id": "pong",
        "cls":     None,
        "module":  "games.pong",
        "class":   "PongGame",
        "modes": [
            ("VS PLAYER", "vs_player"),
            ("VS CPU  EASY",   "easy"),
            ("VS CPU  MED",    "medium"),
            ("VS CPU  HARD",   "hard"),
        ],
        "desc": "First to 11 wins.",
    },
    {
        "label":   "BREAKOUT",
        "game_id": "breakout",
        "cls":     None,
        "module":  "games.breakout",
        "class":   "BreakoutGame",
        "modes": [
            ("CLASSIC", "classic"),
            ("ENDLESS", "endless"),
        ],
        "desc": "Break all the bricks.",
    },
]


def _load_game_class(entry: dict):
    if entry["cls"] is None:
        import importlib
        mod = importlib.import_module(entry["module"])
        entry["cls"] = getattr(mod, entry["class"])
    return entry["cls"]


# ---------------------------------------------------------------------------
# Animated star background
# ---------------------------------------------------------------------------

class _Star:
    __slots__ = ("x", "y", "speed", "size", "alpha")

    def __init__(self):
        self.x     = random.uniform(0, SCREEN_WIDTH)
        self.y     = random.uniform(0, SCREEN_HEIGHT)
        self.speed = random.uniform(8, 40)
        self.size  = random.choice([1, 1, 1, 2])
        self.alpha = random.randint(40, 140)

    def update(self, dt: float):
        self.x -= self.speed * dt
        if self.x < -2:
            self.x = SCREEN_WIDTH + 2
            self.y = random.uniform(0, SCREEN_HEIGHT)

    def draw(self, screen: pygame.Surface):
        r, g, b = colors.FG
        radius = self.size
        diam = radius * 2 + 1
        surf = pygame.Surface((diam, diam), pygame.SRCALPHA)
        pygame.draw.circle(surf, (r, g, b, self.alpha), (radius, radius), radius)
        screen.blit(surf, (int(self.x) - radius, int(self.y) - radius))


_stars: list[_Star] = [_Star() for _ in range(180)]


def _draw_stars(screen: pygame.Surface, dt: float):
    for s in _stars:
        s.update(dt)
        s.draw(screen)


# ---------------------------------------------------------------------------
# Mode selection sub-screen
# ---------------------------------------------------------------------------

def _best_score_label(game_id: str, modes: list) -> str:
    """Return 'BEST: xxx' using the highest score across all modes."""
    best = max(persistence.get_score(game_id, mk) for _, mk in modes)
    if best == 0:
        return "BEST: ---"
    return f"BEST: {int(best)}"


def _run_mode_select(screen: pygame.Surface, clock: pygame.time.Clock, entry: dict) -> str | None:
    """
    Show the mode selection screen for an entry.
    Returns mode key string, or None if the user pressed Escape.
    """
    mode_labels = [m[0] for m in entry["modes"]]
    menu = ui.Menu(mode_labels, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 60, spacing=52)
    transition = ui.Transition(duration=0.2, direction="in")

    while True:
        dt = clock.tick(FPS) / 1000.0
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                return "__quit__"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                return "__quit__"
            result = menu.handle_event(event)
            if result == "ESC":
                return None
            if result is not None:
                # find matching mode key
                for label, key in entry["modes"]:
                    if label == result:
                        return key
                return entry["modes"][0][1]

        # draw
        screen.fill(colors.BG)
        _draw_stars(screen, dt)

        # title
        ui.draw_text(screen, entry["label"], FONT_SIZE_LARGE,
                     SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 160,
                     color=colors.ORANGE)

        # per-mode scores under the menu
        menu.draw(screen)
        for i, (_, mk) in enumerate(entry["modes"]):
            score = persistence.get_score(entry["game_id"], mk)
            score_str = f"{int(score)}" if score > 0 else "---"
            item_y = (SCREEN_HEIGHT // 2 - 60) + i * 52
            ui.draw_text(screen, score_str, FONT_SIZE_TINY,
                         SCREEN_WIDTH // 2 + 220, item_y + 14,
                         color=colors.GREEN, align="left")

        ui.draw_text(screen, "ESC — back", FONT_SIZE_TINY,
                     SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40,
                     color=colors.GREEN)

        ui.draw_fps(screen, clock.get_fps())
        ui.draw_crt(screen)
        transition.update(dt)
        transition.draw(screen)
        pygame.display.flip()


# ---------------------------------------------------------------------------
# Settings overlay
# ---------------------------------------------------------------------------

def _run_settings(screen: pygame.Surface, clock: pygame.time.Clock):
    """Simple settings toggle screen."""
    while True:
        dt = clock.tick(FPS) / 1000.0
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                return "__quit__"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    return
                if event.key == pygame.K_q:
                    return "__quit__"
                if event.key == pygame.K_c:
                    persistence.set_setting("crt_effects",
                        not persistence.get_setting("crt_effects"))
                if event.key == pygame.K_f:
                    persistence.set_setting("show_fps",
                        not persistence.get_setting("show_fps"))

        screen.fill(colors.BG)
        _draw_stars(screen, dt)

        cx = SCREEN_WIDTH // 2
        ui.draw_text(screen, "SETTINGS", FONT_SIZE_LARGE, cx, 160, color=colors.ORANGE)

        crt_on = persistence.get_setting("crt_effects")
        fps_on = persistence.get_setting("show_fps")

        ui.draw_text(screen, f"[C]  CRT effects   {'ON ' if crt_on else 'OFF'}",
                     FONT_SIZE_SMALL, cx, 300,
                     color=colors.BRIGHT_GREEN if crt_on else colors.DIM)
        ui.draw_text(screen, f"[F]  FPS counter   {'ON ' if fps_on else 'OFF'}",
                     FONT_SIZE_SMALL, cx, 350,
                     color=colors.BRIGHT_GREEN if fps_on else colors.DIM)

        ui.draw_text(screen, "ESC — back    Q — quit", FONT_SIZE_TINY, cx,
                     SCREEN_HEIGHT - 40, color=colors.GREEN)

        ui.draw_fps(screen, clock.get_fps())
        ui.draw_crt(screen)
        pygame.display.flip()


# ---------------------------------------------------------------------------
# Launcher main loop
# ---------------------------------------------------------------------------

def _launcher(screen: pygame.Surface, clock: pygame.time.Clock) -> bool:
    """
    Main launcher. Returns True to quit the process, False if a clean exit
    happened through the menu.
    """
    game_labels = [e["label"] for e in _GAME_REGISTRY] + ["SETTINGS"]
    menu = ui.Menu(game_labels, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120, spacing=56)
    transition = ui.Transition(duration=0.35, direction="in")

    # Pulse animation timer
    pulse_t = 0.0
    out_transition: ui.Transition | None = None

    while True:
        dt = clock.tick(FPS) / 1000.0
        pulse_t += dt

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                return True
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F3:
                    persistence.set_setting("show_fps",
                        not persistence.get_setting("show_fps"))
                if event.key == pygame.K_F4:
                    persistence.set_setting("crt_effects",
                        not persistence.get_setting("crt_effects"))
                if event.key == pygame.K_q:
                    return False

            result = menu.handle_event(event)
            if result == "ESC":
                # ESC in launcher = go up one level (no-op at top level — ignore)
                pass

            if result == "SETTINGS":
                ret = _run_settings(screen, clock)
                if ret == "__quit__":
                    return True
                transition = ui.Transition(duration=0.25, direction="in")

            elif result is not None:
                # find game entry
                entry = next((e for e in _GAME_REGISTRY if e["label"] == result), None)
                if entry:
                    mode_key = _run_mode_select(screen, clock, entry)
                    if mode_key == "__quit__":
                        return True
                    if mode_key is not None:
                        # launch the game
                        _launch_game(screen, clock, entry, mode_key)
                    transition = ui.Transition(duration=0.25, direction="in")

        # --- draw ---
        screen.fill(colors.BG)
        _draw_stars(screen, dt)

        # Big title
        title_y = SCREEN_HEIGHT // 2 - 240
        glow_alpha = int(140 + 60 * math.sin(pulse_t * 1.8))
        ui.draw_text(screen, "ARCADE", FONT_SIZE_LARGE + 20,
                     SCREEN_WIDTH // 2, title_y,
                     color=colors.ORANGE, alpha=glow_alpha)
        # game menu
        menu.draw(screen)

        # per-game best score shown to the right of each item
        for i, entry in enumerate(_GAME_REGISTRY):
            best_label = _best_score_label(entry["game_id"], entry["modes"])
            item_y = (SCREEN_HEIGHT // 2 - 120) + i * 56
            ui.draw_text(screen, best_label, FONT_SIZE_TINY,
                         SCREEN_WIDTH // 2 + 230, item_y + 16,
                         color=colors.HIGHLIGHT, align="left")

        # footer hints
        ui.draw_text(screen, "F3 FPS   F4 CRT   Q QUIT",
                     FONT_SIZE_TINY, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 28,
                     color=colors.GREEN)

        ui.draw_fps(screen, clock.get_fps())
        ui.draw_crt(screen)

        transition.update(dt)
        transition.draw(screen)

        pygame.display.flip()


def _launch_game(screen: pygame.Surface, clock: pygame.time.Clock,
                 entry: dict, mode_key: str):
    """Fade out, run the game, return to launcher."""
    # Fade out
    fade = ui.Transition(duration=0.25, direction="out")
    while not fade.done:
        dt = clock.tick(FPS) / 1000.0
        screen.fill(colors.BG)
        fade.update(dt)
        fade.draw(screen)
        pygame.display.flip()

    # Instantiate and run
    cls = _load_game_class(entry)
    game = cls(screen, clock, mode=mode_key)
    game.run()

    # Fade back in handled by the game's own transition (or launcher's)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    pygame.display.set_caption("Arcade")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock  = pygame.time.Clock()

    persistence.load()

    _launcher(screen, clock)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
