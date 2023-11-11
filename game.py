import pyray as rl, glm, util
from types import SimpleNamespace

WIDTH, HEIGHT = 800, 600
rl.init_window(WIDTH, HEIGHT, "My awesome game")

state = SimpleNamespace(player=glm.vec2(10, 10))


def update(state):
    state.player.x += 1


def draw(state):
    rl.clear_background(rl.BLACK)
    rl.draw_rectangle(int(state.player.x), int(state.player.y), 100, 100, rl.RED)


rl.set_target_fps(60)
while not rl.window_should_close():
    update(state)
    rl.begin_drawing()
    rl.draw_fps(10, 10)
    draw(state)
    rl.end_drawing()
