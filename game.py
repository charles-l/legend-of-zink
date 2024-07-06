import pyray as rl
import random
import util

WIDTH, HEIGHT = 800, 600
rl.init_window(WIDTH, HEIGHT, "Game")
rl.init_audio_device()

canvas_rescaler = util.CanvasScaler(WIDTH, HEIGHT, 2)

class Game:
    def update(self):
        ...

    def draw(self):
        rl.draw_rectangle_rec((10, 10, 100, 100), rl.RED)

game = Game()

# run game
try:
    while not rl.window_should_close():
        game.update()

        rl.begin_drawing()
        game.draw()
        rl.end_drawing()
finally:
    rl.close_audio_device()
    rl.close_window()
