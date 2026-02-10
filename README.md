![Gif asteroids demo](./demo/demo.gif)

# Asteroids

A pygame implementation of the classic Asteroids arcade game.

---

## Recent Updates

- Score system with HUD display and high scores
- Lives mechanic with invulnerability frames
- Screen wrapping for seamless gameplay
- Game state management (Menu → Play → Game Over → Restart)
- Player Inertia & Acceleration

---

## Running

With uv installed:

```bash
uv venv
source .venv/bin/activate
uv run main.py
```

---

## Player Controls
- Movement Controls
  - **W** = thrust forward
  - **S** = thrust backward
  - **A** = turn left
  - **D** = turn right
  - **Space** = shoot

---

## Player Mechanics

Objects seamlessly wrap around screen edges for continuous gameplay.

```python
### constants.py
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
```

```python
### circleshape.py
    def update(self, dt):
        # screen wrapping
        from constants import SCREEN_WIDTH, SCREEN_HEIGHT

        if self.position.x > SCREEN_WIDTH + self.radius:
            self.position.x = -self.radius
        elif self.position.x < -self.radius:
            self.position.x = SCREEN_WIDTH + self.radius
        if self.position.y > SCREEN_HEIGHT + self.radius:
            self.position.y = -self.radius
        elif self.position.y < -self.radius:
            self.position.y = SCREEN_HEIGHT + self.radius
```

Player speeds up and slows down dynamically.

```python
### constants.py
PLAYER_ACCELERATION = 550
PLAYER_DRAG = 0.98
```

```python
# player.py
    def update(self, dt):
        self.timer -= dt
        self.invulnerable_timer -= dt

        ...

        if keys[pygame.K_w]:
            self.accelerate(dt)
        if keys[pygame.K_s]:
            self.accelerate(-dt)

      ...

    def accelerate(self, dt):
        unit_vector = pygame.Vector2(0, 1)
        rotated_vector = unit_vector.rotate(self.rotation)
        acceleration_vector = rotated_vector * PLAYER_ACCELERATION * dt
        self.velocity += acceleration_vector
```

Shoot asteroids to destroy them.

```python
### circleshape.py
    def collides_with(self, other):
        distance = self.position.distance_to(other.position)
        minimum = self.radius + other.radius
        return distance <= minimum
```

Large asteroids split into smaller ones when hit.

```python
### asteroid.py
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
```
