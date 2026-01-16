import pygame
from constants import SCREEN_HEIGHT, SCREEN_WIDTH
from logger import log_state
from player import Player

def main():
    print(f"Starting Asteroids with pygame version: {pygame.version.ver}")
    print(f"Screen width: {SCREEN_WIDTH}")
    print(f"Screen height: {SCREEN_HEIGHT}")

    pygame.init()

    clock = pygame.time.Clock()
    dt = 0
    
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    px = SCREEN_WIDTH / 2
    py = SCREEN_HEIGHT / 2
    player = Player(px, py)

    go = True

    while go == True:
        log_state()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        screen.fill("black")

        player.update(dt)
        player.draw(screen)
        
        pygame.display.flip()
        dt = clock.tick(60) / 1000
        print(f"dt = {dt}")


if __name__ == "__main__":
    main()
