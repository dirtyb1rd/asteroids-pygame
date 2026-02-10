import sys
import pygame
from asteroid import Asteroid
from asteroidfield import AsteroidField
from player import Player
from shot import Shot
from constants import SCREEN_HEIGHT, SCREEN_WIDTH, PLAYER_LIVES, INVULNERABILITY_TIME
from logger import log_state, log_event


def draw_text(screen, text, size, x, y, color="white"):
    font = pygame.font.Font(None, size)
    surface = font.render(text, True, color)
    rect = surface.get_rect(center=(x, y))
    screen.blit(surface, rect)


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    state = "MENU"
    score = 0
    high_score = 0

    while True:
        if state == "MENU":
            screen.fill("black")
            draw_text(
                screen, "ASTEROIDS", 100, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 50
            )
            draw_text(
                screen,
                "PRESS ENTER TO START",
                50,
                SCREEN_WIDTH / 2,
                SCREEN_HEIGHT / 2 + 50,
            )
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and (
                    event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER
                ):
                    state = "PLAYING"

                    score = 0
                    lives = PLAYER_LIVES
                    updatable = pygame.sprite.Group()
                    drawable = pygame.sprite.Group()
                    asteroids = pygame.sprite.Group()
                    shots = pygame.sprite.Group()

                    Asteroid.containers = (asteroids, updatable, drawable)
                    AsteroidField.containers = updatable
                    Shot.containers = (shots, updatable, drawable)
                    Player.containers = (updatable, drawable)

                    AsteroidField()
                    player = Player(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)

        elif state == "PLAYING":
            dt = clock.tick(60) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

            screen.fill("black")
            updatable.update(dt)

            for asteroid in asteroids:
                if player.invulnerable_timer <= 0 and asteroid.collides_with(player):
                    log_event("player_hit")
                    lives -= 1
                    if lives <= 0:
                        state = "GAME_OVER"
                        if score > high_score:
                            high_score = score
                    else:
                        player.position = pygame.Vector2(
                            SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2
                        )
                        player.velocity = pygame.Vector2(0, 0)
                        player.invulnerable_timer = INVULNERABILITY_TIME

                for bullet in shots:
                    if asteroid.collides_with(bullet):
                        log_event("asteroid_shot")
                        points = asteroid.split()
                        if points:
                            score += points
                        bullet.kill()

            for obj in drawable:
                obj.draw(screen)

            # hud
            draw_text(screen, f"SCORE: {score}", 30, 70, 30)
            draw_text(screen, f"LIVES: {lives}", 30, 70, 60)

            pygame.display.flip()

        elif state == "GAME_OVER":
            screen.fill("black")
            draw_text(
                screen,
                "GAME OVER",
                100,
                SCREEN_WIDTH / 2,
                SCREEN_HEIGHT / 2 - 50,
                "red",
            )
            draw_text(
                screen,
                f"FINAL SCORE: {score}",
                50,
                SCREEN_WIDTH / 2,
                SCREEN_HEIGHT / 2 + 20,
            )
            draw_text(
                screen,
                f"HIGH SCORE: {high_score}",
                30,
                SCREEN_WIDTH / 2,
                SCREEN_HEIGHT / 2 + 60,
            )
            draw_text(
                screen,
                "PRESS R TO RESTART",
                40,
                SCREEN_WIDTH / 2,
                SCREEN_HEIGHT / 2 + 120,
            )
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    state = "MENU"


if __name__ == "__main__":
    main()
