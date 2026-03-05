from __future__ import annotations

import random
import time

import pygame

import colors
import persistence
import ui
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, FONT_SIZE_LARGE, FONT_SIZE_MEDIUM, FONT_SIZE_SMALL, FONT_SIZE_TINY
from games.base import BaseGame

from .board import Board
from .constants import (
    BOARD_COLS, BOARD_ROWS, CELL_SIZE,
    BOARD_X, BOARD_Y,
    SPRINT_LINES, ULTRA_TIME,
    drop_interval,
)
from .pieces import PIECES, PIECE_NAMES


# Sidebar layout anchors (right of the board)
_SIDE_X = BOARD_X + BOARD_COLS * CELL_SIZE + 24   # left edge of sidebar
_SIDE_W = 160                                       # sidebar width
_SIDE_CX = _SIDE_X + _SIDE_W // 2                  # sidebar center x


def _make_piece(name: str) -> dict:
    """Return a fresh piece dict at spawn position."""
    return {
        "name": name,
        "rotation": 0,
        "col": 3,
        "row": 0,
        "color": PIECES[name]["color"],
    }


def _piece_cells(piece: dict) -> list[tuple[int, int]]:
    """Return absolute (col, row) grid positions for a piece."""
    offsets = PIECES[piece["name"]]["rotations"][piece["rotation"]]
    return [(piece["col"] + dc, piece["row"] + dr) for dc, dr in offsets]


# Wall-kick offsets to try when rotating
_WALL_KICKS = [(0, 0), (1, 0), (-1, 0), (0, -1), (1, -1), (-1, -1)]


class TetrisGame(BaseGame):
    name = "Tetris"
    game_id = "tetris"

    # ------------------------------------------------------------------ #
    #  Construction / lifecycle                                            #
    # ------------------------------------------------------------------ #

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, mode: str = "marathon"):
        super().__init__(screen, clock)
        self.mode = mode

        self.particles = ui.ParticleSystem()
        self.shake = ui.ScreenShake()
        self.transition = ui.Transition(duration=0.4, direction="in")

        self._bag: list[str] = []
        self._reset()

    # ------------------------------------------------------------------ #
    #  Internal reset                                                      #
    # ------------------------------------------------------------------ #

    def _reset(self) -> None:
        self.board = Board()
        self._bag = []

        self.current_piece = _make_piece(self._next_from_bag())
        self.next_piece = _make_piece(self._next_from_bag())
        self.held_piece: dict | None = None
        self.can_hold = True

        self.drop_timer = 0.0
        self.soft_drop = False

        self.paused = False
        self.game_over = False
        self.complete = False   # sprint finished / ultra ended

        # Mode-specific
        self.elapsed_time = 0.0   # ultra / sprint timer

        # High-score tracking
        self._new_record = False

        self.particles.clear()
        self.transition = ui.Transition(duration=0.4, direction="in")

    # ------------------------------------------------------------------ #
    #  7-bag randomizer                                                    #
    # ------------------------------------------------------------------ #

    def _next_from_bag(self) -> str:
        if not self._bag:
            self._bag = PIECE_NAMES[:]
            random.shuffle(self._bag)
        return self._bag.pop()

    # ------------------------------------------------------------------ #
    #  Piece helpers                                                       #
    # ------------------------------------------------------------------ #

    def _get_cells(self, piece: dict) -> list[tuple[int, int]]:
        return _piece_cells(piece)

    def _can_move(self, piece: dict, dc: int, dr: int) -> bool:
        for col, row in _piece_cells(piece):
            nc, nr = col + dc, row + dr
            if not (0 <= nc < BOARD_COLS and 0 <= nr < BOARD_ROWS):
                return False
            if self.board.grid[nr][nc] is not None:
                return False
        return True

    def _can_place(self, piece: dict) -> bool:
        """Check if piece is valid at its current position (no movement)."""
        for col, row in _piece_cells(piece):
            if not (0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS):
                return False
            if self.board.grid[row][col] is not None:
                return False
        return True

    def _can_rotate(self, piece: dict, new_rot: int) -> tuple[bool, int, int]:
        """
        Check rotation validity with wall kicks.
        Returns (success, kick_dc, kick_dr).
        """
        test = dict(piece)
        test["rotation"] = new_rot % 4
        for dc, dr in _WALL_KICKS:
            test["col"] = piece["col"] + dc
            test["row"] = piece["row"] + dr
            if self._can_place(test):
                return True, dc, dr
        return False, 0, 0

    def _ghost_piece(self) -> dict:
        """Return a copy of current_piece dropped as far as possible."""
        ghost = dict(self.current_piece)
        while self._can_move(ghost, 0, 1):
            ghost = dict(ghost)
            ghost["row"] += 1
        return ghost

    def _lock_piece(self) -> None:
        cells = _piece_cells(self.current_piece)
        color = self.current_piece["color"]
        lines = self.board.place_piece(cells, color)

        # Particles on lock
        for col, row in cells:
            px = BOARD_X + col * CELL_SIZE + CELL_SIZE // 2
            py = BOARD_Y + row * CELL_SIZE + CELL_SIZE // 2
            self.particles.emit(px, py, 4, color, speed=80, lifetime=0.5, radius=2)

        if lines > 0:
            self.shake.shake(intensity=5, duration=0.1)
            # Extra particles for line clears
            for r in self.board.flash_rows:
                py = BOARD_Y + r * CELL_SIZE + CELL_SIZE // 2
                self.particles.emit(
                    BOARD_X + BOARD_COLS * CELL_SIZE // 2, py,
                    12 * lines, color, speed=180, lifetime=0.7, radius=3,
                )

        # Advance pieces
        self.current_piece = self.next_piece
        self.next_piece = _make_piece(self._next_from_bag())
        self.can_hold = True

        # Game over: new piece immediately collides
        if not self._can_place(self.current_piece):
            self.game_over = True
            self._handle_game_over()

    def _hard_drop(self) -> None:
        rows_dropped = 0
        while self._can_move(self.current_piece, 0, 1):
            self.current_piece["row"] += 1
            rows_dropped += 1
        self.board.score += rows_dropped * 2
        self._lock_piece()

    def _hold(self) -> None:
        if not self.can_hold:
            return
        if self.held_piece is None:
            self.held_piece = _make_piece(self.current_piece["name"])
            self.current_piece = self.next_piece
            self.next_piece = _make_piece(self._next_from_bag())
        else:
            held_name = self.held_piece["name"]
            self.held_piece = _make_piece(self.current_piece["name"])
            self.current_piece = _make_piece(held_name)
        self.can_hold = False
        self.drop_timer = 0.0

    # ------------------------------------------------------------------ #
    #  High score / completion                                             #
    # ------------------------------------------------------------------ #

    def _handle_game_over(self) -> None:
        """Called when the game ends (game over OR mode completion)."""
        if self.mode == "marathon":
            self._new_record = persistence.set_score("tetris", "marathon", self.board.score)
        elif self.mode == "ultra":
            self._new_record = persistence.set_score("tetris", "ultra", self.board.score)
        elif self.mode == "sprint":
            # Lower time is better; persistence stores 0 as "no record"
            t = self.elapsed_time
            best = persistence.get_score("tetris", "sprint")
            if best == 0 or t < best:
                persistence._scores.setdefault("tetris", {})["sprint"] = t
                persistence.save()
                self._new_record = True

    def _check_mode_complete(self) -> None:
        if self.complete or self.game_over:
            return
        if self.mode == "sprint" and self.board.lines_cleared >= SPRINT_LINES:
            self.complete = True
            self._handle_game_over()
        elif self.mode == "ultra" and self.elapsed_time >= ULTRA_TIME:
            self.complete = True
            self._handle_game_over()

    # ------------------------------------------------------------------ #
    #  BaseGame interface                                                  #
    # ------------------------------------------------------------------ #

    def handle_events(self, events: list[pygame.event.Event]) -> bool:
        for event in events:
            if event.type == pygame.QUIT:
                return False

            if event.type != pygame.KEYDOWN:
                continue

            key = event.key

            # --- Game over / complete screen ---
            if self.game_over or self.complete:
                if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._reset()
                elif key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
                continue

            # --- Pause ---
            if key == pygame.K_q:
                return False

            if self.paused:
                if key in (pygame.K_ESCAPE, pygame.K_SPACE):
                    self.paused = False
                elif key == pygame.K_r:
                    self._reset()
                continue

            if key == pygame.K_ESCAPE:
                self.paused = True
                continue

            # --- In-game controls ---
            if key in (pygame.K_LEFT, pygame.K_a):
                if self._can_move(self.current_piece, -1, 0):
                    self.current_piece["col"] -= 1

            elif key in (pygame.K_RIGHT, pygame.K_d):
                if self._can_move(self.current_piece, 1, 0):
                    self.current_piece["col"] += 1

            elif key in (pygame.K_UP, pygame.K_w):
                new_rot = (self.current_piece["rotation"] + 1) % 4
                ok, dc, dr = self._can_rotate(self.current_piece, new_rot)
                if ok:
                    self.current_piece["rotation"] = new_rot
                    self.current_piece["col"] += dc
                    self.current_piece["row"] += dr

            elif key in (pygame.K_DOWN, pygame.K_s):
                if self._can_move(self.current_piece, 0, 1):
                    self.current_piece["row"] += 1
                    self.board.score += 1

            elif key == pygame.K_SPACE:
                self._hard_drop()

            elif key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
                self._hold()

        # Track soft drop via held keys
        keys = pygame.key.get_pressed()
        self.soft_drop = bool(keys[pygame.K_DOWN] or keys[pygame.K_s])

        return True

    def update(self, dt: float) -> None:
        self.transition.update(dt)
        self.shake.update(dt)
        self.particles.update(dt)
        self.board.update(dt)

        if self.game_over or self.complete or self.paused:
            return

        # Mode timers
        self.elapsed_time += dt
        self._check_mode_complete()

        if self.complete:
            return

        # Auto-drop
        level = self.board.level
        interval = drop_interval(level)
        if self.soft_drop:
            interval /= 10.0

        self.drop_timer += dt
        if self.drop_timer >= interval:
            self.drop_timer = 0.0
            if self._can_move(self.current_piece, 0, 1):
                self.current_piece["row"] += 1
                if self.soft_drop:
                    self.board.score += 1
            else:
                self._lock_piece()

    def draw(self) -> None:
        ox, oy = self.shake.get_offset()

        # --- Background ---
        self.screen.fill(colors.BG)

        # We draw everything onto a temp surface so we can apply shake offset
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(colors.BG)

        # Board
        self.board.draw(surf)

        # Ghost piece
        if not self.game_over and not self.complete:
            self._draw_ghost(surf)
            self._draw_current_piece(surf)

        # Sidebar
        self._draw_sidebar(surf)

        # Particles
        self.particles.draw(surf)

        # Blit with shake offset
        self.screen.blit(surf, (ox, oy))

        # Overlays (drawn directly on screen, no shake)
        if self.paused:
            self._draw_pause_overlay()
        elif self.game_over:
            self._draw_gameover_overlay()
        elif self.complete:
            self._draw_complete_overlay()

        ui.draw_fps(self.screen, self.clock.get_fps())
        ui.draw_mode_label(self.screen, self.mode.upper())
        ui.draw_crt(self.screen)
        self.transition.draw(self.screen)

    # ------------------------------------------------------------------ #
    #  Drawing helpers                                                     #
    # ------------------------------------------------------------------ #

    def _draw_cell(self, surf: pygame.Surface, col: int, row: int, color: tuple, alpha: int = 255) -> None:
        x = BOARD_X + col * CELL_SIZE
        y = BOARD_Y + row * CELL_SIZE
        if alpha < 255:
            cell_surf = pygame.Surface((CELL_SIZE - 2, CELL_SIZE - 2), pygame.SRCALPHA)
            r, g, b = color[:3]
            cell_surf.fill((r, g, b, alpha))
            surf.blit(cell_surf, (x + 1, y + 1))
        else:
            rect = pygame.Rect(x + 1, y + 1, CELL_SIZE - 2, CELL_SIZE - 2)
            pygame.draw.rect(surf, color, rect)
            pygame.draw.rect(surf, colors.WHITE, rect, 1)

    def _draw_ghost(self, surf: pygame.Surface) -> None:
        ghost = self._ghost_piece()
        color = self.current_piece["color"]
        for col, row in _piece_cells(ghost):
            if 0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS:
                self._draw_cell(surf, col, row, color, alpha=50)

    def _draw_current_piece(self, surf: pygame.Surface) -> None:
        piece = self.current_piece
        for col, row in _piece_cells(piece):
            if 0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS:
                self._draw_cell(surf, col, row, piece["color"])

    def _draw_piece_preview(
        self, surf: pygame.Surface, name: str, cx: int, cy: int, grayed: bool = False
    ) -> None:
        """Draw a piece centered at pixel (cx, cy) in a 4x4 preview area."""
        offsets = PIECES[name]["rotations"][0]
        color = PIECES[name]["color"] if not grayed else colors.DIM
        # Find bounding box to center
        min_c = min(dc for dc, dr in offsets)
        max_c = max(dc for dc, dr in offsets)
        min_r = min(dr for dc, dr in offsets)
        max_r = max(dr for dc, dr in offsets)
        w = (max_c - min_c + 1) * CELL_SIZE
        h = (max_r - min_r + 1) * CELL_SIZE
        ox = cx - w // 2
        oy = cy - h // 2
        for dc, dr in offsets:
            x = ox + (dc - min_c) * CELL_SIZE
            y = oy + (dr - min_r) * CELL_SIZE
            r = pygame.Rect(x + 1, y + 1, CELL_SIZE - 2, CELL_SIZE - 2)
            pygame.draw.rect(surf, color, r)
            if not grayed:
                pygame.draw.rect(surf, colors.WHITE, r, 1)

    def _draw_sidebar(self, surf: pygame.Surface) -> None:
        cx = _SIDE_CX
        font_s = FONT_SIZE_SMALL
        font_t = FONT_SIZE_TINY

        y = BOARD_Y + 10

        # --- NEXT ---
        ui.draw_text(surf, "NEXT", font_t, cx, y, color=colors.GREEN, align="center")
        y += 22
        self._draw_piece_preview(surf, self.next_piece["name"], cx, y + 40)
        y += 90

        # --- HOLD ---
        ui.draw_text(surf, "HOLD", font_t, cx, y, color=colors.GREEN, align="center")
        y += 22
        if self.held_piece is not None:
            self._draw_piece_preview(surf, self.held_piece["name"], cx, y + 40, grayed=not self.can_hold)
        else:
            ui.draw_text(surf, "-", font_t, cx, y + 40, color=colors.DIM, align="center")
        y += 90

        # Divider
        pygame.draw.line(surf, colors.DIM, (_SIDE_X, y), (_SIDE_X + _SIDE_W, y), 1)
        y += 12

        # --- SCORE ---
        ui.draw_text(surf, "SCORE", font_t, cx, y, color=colors.GREEN, align="center")
        y += 20
        ui.draw_text(surf, str(self.board.score), font_s, cx, y, color=colors.ORANGE, align="center")
        y += 32

        # --- LEVEL ---
        ui.draw_text(surf, "LEVEL", font_t, cx, y, color=colors.GREEN, align="center")
        y += 20
        ui.draw_text(surf, str(self.board.level), font_s, cx, y, color=colors.BRIGHT_GREEN, align="center")
        y += 32

        # --- LINES ---
        ui.draw_text(surf, "LINES", font_t, cx, y, color=colors.GREEN, align="center")
        y += 20
        ui.draw_text(surf, str(self.board.lines_cleared), font_s, cx, y, color=colors.BRIGHT_GREEN, align="center")
        y += 32

        # --- Mode-specific info ---
        if self.mode == "sprint":
            remaining = max(0, SPRINT_LINES - self.board.lines_cleared)
            ui.draw_text(surf, "LEFT", font_t, cx, y, color=colors.GREEN, align="center")
            y += 20
            ui.draw_text(surf, str(remaining), font_s, cx, y, color=colors.YELLOW, align="center")
            y += 32
            # Elapsed time
            ui.draw_text(surf, "TIME", font_t, cx, y, color=colors.GREEN, align="center")
            y += 20
            mins = int(self.elapsed_time) // 60
            secs = int(self.elapsed_time) % 60
            cs = int((self.elapsed_time % 1) * 100)
            ui.draw_text(surf, f"{mins:02d}:{secs:02d}.{cs:02d}", font_t, cx, y, color=colors.BRIGHT_GREEN, align="center")

        elif self.mode == "ultra":
            remaining = max(0.0, ULTRA_TIME - self.elapsed_time)
            ui.draw_text(surf, "TIME", font_t, cx, y, color=colors.GREEN, align="center")
            y += 20
            mins = int(remaining) // 60
            secs = int(remaining) % 60
            time_color = colors.BRIGHT_RED if remaining < 30 else colors.YELLOW
            ui.draw_text(surf, f"{mins:02d}:{secs:02d}", font_s, cx, y, color=time_color, align="center")

        # --- Best score (bottom of sidebar) ---
        y_best = BOARD_Y + BOARD_ROWS * CELL_SIZE - 50
        if self.mode == "sprint":
            best_raw = persistence.get_score("tetris", "sprint")
            if best_raw > 0:
                bm = int(best_raw) // 60
                bs = int(best_raw) % 60
                bcs = int((best_raw % 1) * 100)
                ui.draw_text(surf, "BEST", font_t, cx, y_best, color=colors.GREEN, align="center")
                ui.draw_text(surf, f"{bm:02d}:{bs:02d}.{bcs:02d}", font_t, cx, y_best + 18, color=colors.GREEN, align="center")
        else:
            best = persistence.get_score("tetris", self.mode)
            if best > 0:
                ui.draw_text(surf, "BEST", font_t, cx, y_best, color=colors.GREEN, align="center")
                ui.draw_text(surf, str(int(best)), font_t, cx, y_best + 18, color=colors.GREEN, align="center")

    def _draw_overlay(self, title: str, lines: list[str]) -> None:
        """Draw a centered semi-transparent overlay panel."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        y = SCREEN_HEIGHT // 2 - 80

        ui.draw_text(self.screen, title, FONT_SIZE_LARGE, cx, y, color=colors.WHITE)
        y += FONT_SIZE_LARGE + 16
        for line in lines:
            ui.draw_text(self.screen, line, FONT_SIZE_SMALL, cx, y, color=colors.GREEN)
            y += FONT_SIZE_SMALL + 8

    def _draw_pause_overlay(self) -> None:
        self._draw_overlay("PAUSED", ["SPACE / ESC  resume", "R  restart       Q  menu"])

    def _draw_gameover_overlay(self) -> None:
        extras = [f"SCORE  {self.board.score}"]
        if self._new_record:
            extras.append("NEW RECORD!")
        extras += ["", "R / ENTER  restart       Q / ESC  menu"]
        self._draw_overlay("GAME OVER", extras)

    def _draw_complete_overlay(self) -> None:
        if self.mode == "sprint":
            mins = int(self.elapsed_time) // 60
            secs = int(self.elapsed_time) % 60
            cs = int((self.elapsed_time % 1) * 100)
            result_str = f"TIME  {mins:02d}:{secs:02d}.{cs:02d}"
        else:
            result_str = f"SCORE  {self.board.score}"

        extras = [result_str]
        if self._new_record:
            extras.append("NEW RECORD!")
        extras += ["", "R / ENTER  restart       Q / ESC  menu"]

        title = "SPRINT CLEAR!" if self.mode == "sprint" else "TIME UP!"
        self._draw_overlay(title, extras)
