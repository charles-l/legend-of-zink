import pyray as rl
import random

WIDTH, HEIGHT = 800, 600
rl.init_window(WIDTH, HEIGHT, "Flappy")
rl.init_audio_device()

# run game
try:
    while not rl.window_should_close():
        # update
        rl.begin_drawing()
        # draw
        rl.end_drawing()
finally:
    rl.close_audio_device()
    rl.close_window()
