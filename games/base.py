import pygame
from abc import ABC, abstractmethod


class BaseGame(ABC):
    """Abstract base for all mini-games.

    Subclasses implement handle_events(), update(), and draw().
    Call run() to execute the game loop. When run() returns, control
    passes back to the launcher.
    """

    name: str = "Unnamed"
    game_id: str = ""   # used as persistence key e.g. "asteroids"

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        self.screen  = screen
        self.clock   = clock
        self.running = True
        self.width   = screen.get_width()
        self.height  = screen.get_height()

    @abstractmethod
    def handle_events(self, events: list[pygame.event.Event]) -> bool:
        """Process events. Return False to exit to launcher."""
        ...

    @abstractmethod
    def update(self, dt: float) -> None:
        """Update game state. dt is seconds since last frame."""
        ...

    @abstractmethod
    def draw(self) -> None:
        """Render the current frame to self.screen."""
        ...

    def on_enter(self) -> None:
        """Called once before the game loop starts."""
        pass

    def on_exit(self) -> None:
        """Called once after the game loop ends."""
        pass

    def run(self) -> None:
        """Run the game loop until handle_events returns False."""
        from constants import FPS
        self.on_enter()
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            events = pygame.event.get()
            if not self.handle_events(events):
                break
            self.update(dt)
            self.draw()
            pygame.display.flip()
        self.on_exit()
