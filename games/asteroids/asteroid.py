import pygame
import random
import colors
from constants import LINE_WIDTH
from .circleshape import CircleShape
from .constants import (
    ASTEROID_MIN_RADIUS,
    ASTEROID_SCORE_LARGE,
    ASTEROID_SCORE_MEDIUM,
    ASTEROID_SCORE_SMALL,
)
from logger import log_event


class Asteroid(CircleShape):
    speed_mult: float = 1.0   # set per-game-instance via class attr

    def __init__(self, x, y, radius):
        super().__init__(x, y, radius)

    def draw(self, screen):
        pygame.draw.circle(screen, colors.HIGHLIGHT, self.position, self.radius)
        pygame.draw.circle(screen, colors.ORANGE, self.position, self.radius, LINE_WIDTH)

    def update(self, dt):
        super().update(dt)
        self.position += self.velocity * dt

    def split(self) -> int:
        self.kill()
        if self.radius <= ASTEROID_MIN_RADIUS:
            return ASTEROID_SCORE_SMALL
        log_event("asteroid_split")
        angle = random.uniform(20, 50)
        v1 = self.velocity.rotate(angle) * 1.2 * self.speed_mult
        v2 = self.velocity.rotate(-angle) * 1.2 * self.speed_mult
        new_radius = self.radius - ASTEROID_MIN_RADIUS
        a1 = Asteroid(self.position.x, self.position.y, new_radius)
        a1.velocity = v1
        a2 = Asteroid(self.position.x, self.position.y, new_radius)
        a2.velocity = v2
        return (
            ASTEROID_SCORE_LARGE if new_radius > ASTEROID_MIN_RADIUS
            else ASTEROID_SCORE_MEDIUM
        )
