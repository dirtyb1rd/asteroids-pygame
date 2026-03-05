"""
ui.py — shared UI module for the retro arcade collection.

Provides: font cache, draw_text, CRT overlays, Transition, Menu,
HUD helpers, draw_fps, ParticleSystem, ScreenShake.
"""
from __future__ import annotations

import math
import random

import pygame

import colors
import persistence
from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FONT_SIZE_LARGE,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
)

# ---------------------------------------------------------------------------
# 1. Font cache
# ---------------------------------------------------------------------------

_font_cache: dict = {}  # int -> pygame.font.Font

# Resolved once on first call; None means fall back to default font.
_font_path: str | None = "__unresolved__"


def _resolve_font_path() -> str | None:
    global _font_path
    if _font_path == "__unresolved__":
        _font_path = pygame.font.match_font(
            "courier,couriernew,monospace,dejavusansmono"
        )
    return _font_path


def get_font(size: int) -> pygame.font.Font:
    """Return a cached monospace font at *size* points."""
    if not pygame.font.get_init():
        pygame.font.init()
    if size not in _font_cache:
        path = _resolve_font_path()
        _font_cache[size] = pygame.font.Font(path, size)
    return _font_cache[size]


# ---------------------------------------------------------------------------
# 2. draw_text
# ---------------------------------------------------------------------------

def draw_text(
    screen: pygame.Surface,
    text: str,
    size: int,
    x: int,
    y: int,
    color: tuple = colors.FG,
    align: str = "center",
    alpha: int = 255,
) -> pygame.Rect:
    """
    Render *text* onto *screen*.

    align: "center" | "left" | "right"
    alpha: 0-255; values < 255 render via a temp surface.

    Returns the blit rect.
    """
    font = get_font(size)
    surf = font.render(text, True, color)

    if align == "center":
        rect = surf.get_rect(centerx=x, top=y)
    elif align == "right":
        rect = surf.get_rect(right=x, top=y)
    else:  # "left"
        rect = surf.get_rect(left=x, top=y)

    if alpha < 255:
        tmp = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        tmp.blit(surf, (0, 0))
        tmp.set_alpha(alpha)
        screen.blit(tmp, rect)
    else:
        screen.blit(surf, rect)

    return rect


# ---------------------------------------------------------------------------
# 3. CRT effects
# ---------------------------------------------------------------------------

_scanline_surf: pygame.Surface | None = None
_vignette_surf: pygame.Surface | None = None


def _build_scanlines() -> pygame.Surface:
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    line_color = (0, 0, 0, 40)
    for y in range(0, SCREEN_HEIGHT, 3):
        pygame.draw.line(surf, line_color, (0, y), (SCREEN_WIDTH - 1, y))
    return surf


def _build_vignette() -> pygame.Surface:
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))

    cx = SCREEN_WIDTH // 2
    cy = SCREEN_HEIGHT // 2
    steps = 30
    # Each step draws an ellipse shrinking inward by ~8px per axis per step.
    # Outermost ellipse (i=0) is full-screen and most opaque.
    for i in range(steps):
        alpha = int(160 * (1 - i / steps))
        # Shrink the ellipse rect by 8px per step on each side
        margin_x = i * 8
        margin_y = i * 8
        rect = pygame.Rect(
            margin_x,
            margin_y,
            SCREEN_WIDTH - margin_x * 2,
            SCREEN_HEIGHT - margin_y * 2,
        )
        if rect.width <= 0 or rect.height <= 0:
            break
        # Draw only the border of each ellipse band so the center stays clear.
        # We use width=8 to fill the ring between this ellipse and the next.
        pygame.draw.ellipse(surf, (0, 0, 0, alpha), rect, 8)

    return surf


def _ensure_crt_surfs() -> None:
    global _scanline_surf, _vignette_surf
    if _scanline_surf is None:
        _scanline_surf = _build_scanlines()
    if _vignette_surf is None:
        _vignette_surf = _build_vignette()


def draw_crt(screen: pygame.Surface) -> None:
    """Blit CRT overlays if the 'crt_effects' setting is enabled."""
    if not persistence.get_setting("crt_effects"):
        return
    _ensure_crt_surfs()
    screen.blit(_scanline_surf, (0, 0))
    screen.blit(_vignette_surf, (0, 0))


# ---------------------------------------------------------------------------
# 4. Transition
# ---------------------------------------------------------------------------

class Transition:
    """
    Fade transition overlay.

    direction="in"  → fade from black to transparent (scene reveals)
    direction="out" → fade from transparent to black  (scene hides)
    """

    def __init__(self, duration: float = 0.35, direction: str = "in"):
        self._duration = max(duration, 0.001)
        self._direction = direction
        self._elapsed = 0.0
        self._done = False

    def update(self, dt: float) -> bool:
        """Advance the transition. Returns True when complete."""
        if self._done:
            return True
        self._elapsed += dt
        if self._elapsed >= self._duration:
            self._elapsed = self._duration
            self._done = True
        return self._done

    def draw(self, screen: pygame.Surface) -> None:
        t = min(self._elapsed / self._duration, 1.0)
        if self._direction == "in":
            # Start opaque, fade to transparent
            alpha = int(255 * (1.0 - t))
        else:
            # Start transparent, fade to opaque
            alpha = int(255 * t)

        if alpha <= 0:
            return

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(alpha)
        screen.blit(overlay, (0, 0))

    @property
    def done(self) -> bool:
        return self._done


# ---------------------------------------------------------------------------
# 5. Menu
# ---------------------------------------------------------------------------

class Menu:
    """Vertical selectable list with keyboard navigation."""

    def __init__(
        self,
        items: list[str],
        x: int,
        y: int,
        font_size: int = FONT_SIZE_MEDIUM,
        spacing: int = 60,
    ):
        self.items = items
        self.x = x
        self.y = y
        self.font_size = font_size
        self.spacing = spacing
        self.selected: int = 0

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """
        Process a pygame event.

        Returns:
          - The selected item string when RETURN is pressed.
          - "ESC" when ESCAPE is pressed.
          - None otherwise.
        """
        if event.type != pygame.KEYDOWN:
            return None

        if event.key == pygame.K_UP:
            self.selected = (self.selected - 1) % len(self.items)
        elif event.key == pygame.K_DOWN:
            self.selected = (self.selected + 1) % len(self.items)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self.items[self.selected]
        elif event.key == pygame.K_ESCAPE:
            return "ESC"

        return None

    def draw(self, screen: pygame.Surface) -> None:
        for i, item in enumerate(self.items):
            item_y = self.y + i * self.spacing
            is_selected = i == self.selected

            if is_selected:
                text_color = colors.WHITE
                prefix = "> "
            else:
                text_color = colors.DIM
                prefix = "  "

            label = prefix + item

            # Draw prefix in HIGHLIGHT color, item text separately for
            # accurate positioning.  Simpler: render the full prefixed string
            # but colorize the ">" separately.
            font = get_font(self.font_size)

            # Measure prefix width so we can split colors
            prefix_surf = font.render(prefix, True, colors.HIGHLIGHT)
            item_surf = font.render(item, True, text_color)

            total_w = prefix_surf.get_width() + item_surf.get_width()
            start_x = self.x - total_w // 2  # center the combined label

            screen.blit(prefix_surf, (start_x, item_y))
            screen.blit(item_surf, (start_x + prefix_surf.get_width(), item_y))

            # Subtle underline below selected item
            if is_selected:
                line_y = item_y + self.font_size + 4
                line_x0 = start_x
                line_x1 = start_x + total_w
                underline_surf = pygame.Surface((line_x1 - line_x0, 2), pygame.SRCALPHA)
                r, g, b = colors.HIGHLIGHT
                underline_surf.fill((r, g, b, int(255 * 0.6)))
                screen.blit(underline_surf, (line_x0, line_y))


# ---------------------------------------------------------------------------
# 6. HUD helpers
# ---------------------------------------------------------------------------

def draw_score(screen: pygame.Surface, score: int, label: str = "SCORE") -> None:
    """Top-left: label above score value, green."""
    draw_text(screen, label, FONT_SIZE_SMALL, 80, 18, color=colors.GREEN, align="left")
    draw_text(screen, str(score), FONT_SIZE_MEDIUM, 80, 42, color=colors.BRIGHT_GREEN, align="left")


def draw_lives(screen: pygame.Surface, lives: int, label: str = "LIVES") -> None:
    """Top-left below score: label above value, green."""
    draw_text(screen, label, FONT_SIZE_SMALL, 80, 90, color=colors.GREEN, align="left")
    draw_text(screen, str(lives), FONT_SIZE_MEDIUM, 80, 114, color=colors.BRIGHT_GREEN, align="left")


def draw_high_score(screen: pygame.Surface, high: int, label: str = "BEST") -> None:
    """Top-right: mirrored layout of draw_score."""
    x = SCREEN_WIDTH - 80
    draw_text(screen, label, FONT_SIZE_SMALL, x, 18, color=colors.GREEN, align="right")
    draw_text(screen, str(high), FONT_SIZE_MEDIUM, x, 42, color=colors.BRIGHT_GREEN, align="right")


def draw_timer(screen: pygame.Surface, seconds: float) -> None:
    """Top-center: elapsed/remaining time as MM:SS, green."""
    total = max(0, int(seconds))
    mins = total // 60
    secs = total % 60
    text = f"{mins:02d}:{secs:02d}"
    draw_text(screen, text, FONT_SIZE_MEDIUM, SCREEN_WIDTH // 2, 18, color=colors.BRIGHT_GREEN)


# ---------------------------------------------------------------------------
# 7. draw_fps
# ---------------------------------------------------------------------------

def draw_fps(screen: pygame.Surface, fps: float) -> None:
    """Bottom-right: FPS counter shown only when 'show_fps' setting is True."""
    if not persistence.get_setting("show_fps"):
        return
    text = f"{fps:.0f} FPS"
    draw_text(
        screen,
        text,
        FONT_SIZE_SMALL,
        SCREEN_WIDTH - 8,
        SCREEN_HEIGHT - FONT_SIZE_SMALL - 8,
        color=colors.GREEN,
        align="right",
    )


def draw_mode_label(screen: pygame.Surface, label: str) -> None:
    """Bottom-center: game mode label, green."""
    draw_text(
        screen,
        label,
        FONT_SIZE_SMALL,
        SCREEN_WIDTH // 2,
        SCREEN_HEIGHT - FONT_SIZE_SMALL - 8,
        color=colors.GREEN,
        align="center",
    )


# ---------------------------------------------------------------------------
# 8. Particle system
# ---------------------------------------------------------------------------

class Particle:
    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        color: tuple,
        lifetime: float = 0.8,
        radius: float = 3,
    ):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.lifetime = lifetime
        self._max_lifetime = lifetime
        self.radius = radius
        self._max_radius = radius

    def update(self, dt: float) -> bool:
        """Move and age the particle. Returns True while still alive."""
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.lifetime -= dt
        if self.lifetime <= 0:
            return False
        # Shrink radius proportionally to remaining lifetime
        t = self.lifetime / self._max_lifetime
        self.radius = self._max_radius * t
        return True

    def draw(self, screen: pygame.Surface) -> None:
        r = max(1, int(self.radius))
        t = max(0.0, self.lifetime / self._max_lifetime)
        alpha = int(255 * t)

        # Draw onto a small SRCALPHA surface centered on particle position
        size = r * 2 + 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cr, cg, cb = self.color[:3]
        pygame.draw.circle(surf, (cr, cg, cb, alpha), (size // 2, size // 2), r)
        screen.blit(surf, (int(self.x) - size // 2, int(self.y) - size // 2))


class ParticleSystem:
    def __init__(self):
        self._particles: list[Particle] = []

    def emit(
        self,
        x: float,
        y: float,
        count: int,
        color: tuple,
        speed: float = 150,
        lifetime: float = 0.8,
        radius: float = 3,
    ) -> None:
        """Spawn *count* particles at (x, y) in random directions."""
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            spd = speed * random.uniform(0.5, 1.5)
            vx = math.cos(angle) * spd
            vy = math.sin(angle) * spd
            self._particles.append(Particle(x, y, vx, vy, color, lifetime, radius))

    def update(self, dt: float) -> None:
        self._particles = [p for p in self._particles if p.update(dt)]

    def draw(self, screen: pygame.Surface) -> None:
        for p in self._particles:
            p.draw(screen)

    def clear(self) -> None:
        self._particles.clear()

    def __len__(self) -> int:
        return len(self._particles)


# ---------------------------------------------------------------------------
# 9. ScreenShake
# ---------------------------------------------------------------------------

class ScreenShake:
    def __init__(self):
        self._timer: float = 0.0
        self._duration: float = 0.15
        self._intensity: int = 0

    def shake(self, intensity: int = 8, duration: float = 0.15) -> None:
        """Trigger a screen shake with the given intensity and duration."""
        self._intensity = intensity
        self._duration = duration
        self._timer = duration

    def update(self, dt: float) -> None:
        self._timer = max(0.0, self._timer - dt)

    def get_offset(self) -> tuple[int, int]:
        """Return a (dx, dy) pixel offset to apply to the camera/blit origin."""
        if self._timer <= 0:
            return (0, 0)
        # Scale intensity down linearly as timer drains toward zero
        scale = self._timer / self._duration
        i = max(1, int(self._intensity * scale))
        return (random.randint(-i, i), random.randint(-i, i))
