import pygame
import colors
from constants import LINE_WIDTH
from .circleshape import CircleShape
from .shot import Shot
from .constants import (
    PLAYER_RADIUS,
    PLAYER_TURN_SPEED,
    PLAYER_SHOOT_SPEED,
    PLAYER_SHOOT_COOLDOWN,
    PLAYER_ACCELERATION,
    PLAYER_DRAG,
    INVULNERABILITY_TIME,
)


class Player(CircleShape):
    def __init__(self, x, y):
        super().__init__(x, y, PLAYER_RADIUS)
        self.rotation = 0
        self.timer = 0
        self.invulnerable_timer = INVULNERABILITY_TIME

    def triangle(self):
        forward = pygame.Vector2(0, 1).rotate(self.rotation)
        right = pygame.Vector2(0, 1).rotate(self.rotation + 90) * self.radius / 1.5
        a = self.position + forward * self.radius
        b = self.position - forward * self.radius - right
        c = self.position - forward * self.radius + right
        return [a, b, c]

    def draw(self, screen):
        if self.invulnerable_timer > 0 and int(self.invulnerable_timer * 10) % 2 == 0:
            return
        pygame.draw.polygon(screen, colors.BRIGHT_GREEN, self.triangle())
        pygame.draw.polygon(screen, colors.WHITE, self.triangle(), LINE_WIDTH)

    def rotate(self, dt):
        self.rotation += PLAYER_TURN_SPEED * dt

    def update(self, dt):
        self.timer -= dt
        self.invulnerable_timer -= dt
        super().update(dt)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.rotate(-dt)
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.rotate(dt)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.accelerate(dt)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.accelerate(-dt)
        if keys[pygame.K_SPACE]:
            self.shoot()
        self.position += self.velocity * dt
        self.velocity *= PLAYER_DRAG

    def accelerate(self, dt):
        unit_vector = pygame.Vector2(0, 1)
        rotated = unit_vector.rotate(self.rotation)
        self.velocity += rotated * PLAYER_ACCELERATION * dt

    def shoot(self):
        if self.timer > 0:
            return
        self.timer = PLAYER_SHOOT_COOLDOWN
        shot = Shot(self.position.x, self.position.y)
        shot.velocity = pygame.Vector2(0, 1).rotate(self.rotation) * PLAYER_SHOOT_SPEED
