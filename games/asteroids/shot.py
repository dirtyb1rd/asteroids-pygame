import pygame
import colors
from constants import LINE_WIDTH
from .circleshape import CircleShape
from .constants import SHOT_RADIUS, SHOT_LIFETIME


class Shot(CircleShape):
    def __init__(self, x, y):
        super().__init__(x, y, SHOT_RADIUS)
        self._lifetime = SHOT_LIFETIME

    def draw(self, screen):
        pygame.draw.circle(screen, colors.YELLOW, self.position, self.radius)
        pygame.draw.circle(screen, colors.WHITE, self.position, self.radius, LINE_WIDTH)

    def update(self, dt):
        super().update(dt)
        self._lifetime -= dt
        if self._lifetime <= 0:
            self.kill()
            return
        self.position += self.velocity * dt
