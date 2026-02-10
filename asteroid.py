import pygame
from constants import (
    LINE_WIDTH,
    ASTEROID_MIN_RADIUS,
    ASTEROID_SCORE_LARGE,
    ASTEROID_SCORE_MEDIUM,
    ASTEROID_SCORE_SMALL,
)
from circleshape import CircleShape
from logger import log_event
import random


class Asteroid(CircleShape):
    def __init__(self, x, y, radius):
        super().__init__(x, y, radius)

    def draw(self, screen):
        pygame.draw.circle(screen, "lightgray", self.position, self.radius)
        pygame.draw.circle(screen, "darkgray", self.position, self.radius, LINE_WIDTH)

    def update(self, dt):
        super().update(dt)  # wrapping
        self.position += self.velocity * dt

    def split(self):
        self.kill()

        if self.radius <= ASTEROID_MIN_RADIUS:
            return ASTEROID_SCORE_SMALL

        log_event("asteroid_split")

        angle = random.uniform(20, 50)
        vector_1 = self.velocity.rotate(angle)
        vector_2 = self.velocity.rotate(-angle)

        new_radius = self.radius - ASTEROID_MIN_RADIUS

        new_1 = Asteroid(self.position.x, self.position.y, new_radius)
        new_1.velocity = vector_1 * 1.2
        new_2 = Asteroid(self.position.x, self.position.y, new_radius)
        new_2.velocity = vector_2 * 1.2

        return (
            ASTEROID_SCORE_LARGE
            if new_radius > ASTEROID_MIN_RADIUS
            else ASTEROID_SCORE_MEDIUM
        )
