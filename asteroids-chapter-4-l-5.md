Okay, so bullets are flying, but they don't do anything. Let's kill some asteroids!

There are three types of asteroids:

Large
Medium
Small
When a large asteroid is destroyed, it should split into two medium asteroids. When a medium asteroid is destroyed, it should split into two small asteroids. When a small asteroid is destroyed, it should disappear.

For now, we'll just always make the asteroids disappear when they're destroyed. We'll handle splitting later.

Assignment
Add another collision check to the game loop. Loop over each asteroid, and for each asteroid, loop over each shot. If a shot and an asteroid collide:
Call log_event("asteroid_shot").
Call the .kill() method on both objects (the shot and the asteroid) to remove them from the game.
The kill() method is a built-in feature of pygame sprites. It removes the "killed" object from all of its groups so that the engine stops updating and drawing it.

Run the game for at least a few seconds, and make sure you can destroy asteroids by shooting them.
If everything looks right, run and submit the CLI tests.
