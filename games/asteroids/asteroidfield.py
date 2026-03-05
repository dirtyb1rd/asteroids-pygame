import pygame
import random
from constants import SCREEN_WIDTH, SCREEN_HEIGHT
from .asteroid import Asteroid
from .constants import (
    ASTEROID_KINDS,
    ASTEROID_MAX_RADIUS,
    ASTEROID_MIN_RADIUS,
    ASTEROID_SPAWN_RATE,
    ASTEROID_SPEED_MIN,
    ASTEROID_SPEED_MAX,
)


class AsteroidField(pygame.sprite.Sprite):
    edges = [
        [pygame.Vector2(1, 0),  lambda y: pygame.Vector2(-ASTEROID_MAX_RADIUS, y * SCREEN_HEIGHT)],
        [pygame.Vector2(-1, 0), lambda y: pygame.Vector2(SCREEN_WIDTH + ASTEROID_MAX_RADIUS, y * SCREEN_HEIGHT)],
        [pygame.Vector2(0, 1),  lambda x: pygame.Vector2(x * SCREEN_WIDTH, -ASTEROID_MAX_RADIUS)],
        [pygame.Vector2(0, -1), lambda x: pygame.Vector2(x * SCREEN_WIDTH, SCREEN_HEIGHT + ASTEROID_MAX_RADIUS)],
    ]

    def __init__(self, spawn_rate=ASTEROID_SPAWN_RATE, speed_mult=1.0):
        pygame.sprite.Sprite.__init__(self, self.containers)
        self.spawn_timer = 0.0
        self.spawn_rate = spawn_rate
        self.speed_mult = speed_mult

    def spawn(self, radius, position, velocity):
        a = Asteroid(position.x, position.y, radius)
        a.velocity = velocity

    def update(self, dt):
        self.spawn_timer += dt
        if self.spawn_timer > self.spawn_rate:
            self.spawn_timer = 0
            edge = random.choice(self.edges)
            speed = random.randint(ASTEROID_SPEED_MIN, ASTEROID_SPEED_MAX) * self.speed_mult
            velocity = edge[0] * speed
            velocity = velocity.rotate(random.randint(-30, 30))
            position = edge[1](random.uniform(0, 1))
            kind = random.randint(1, ASTEROID_KINDS)
            self.spawn(ASTEROID_MIN_RADIUS * kind, position, velocity)
