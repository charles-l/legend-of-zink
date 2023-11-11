import pyray as rl, glm, util
from types import SimpleNamespace

WIDTH, HEIGHT = 800, 600
rl.init_window(WIDTH, HEIGHT, "My awesome game")

state = SimpleNamespace(player=glm.vec2(10, 10))


def update(state):
    input = glm.vec2()
    if rl.is_key_down(rl.KEY_DOWN): input.y += 1
    if rl.is_key_down(rl.KEY_UP): input.y -= 1
    if rl.is_key_down(rl.KEY_LEFT): input.x -= 1
    if rl.is_key_down(rl.KEY_RIGHT): input.x += 1

    input.x += rl.get_gamepad_axis_movement(0, rl.GAMEPAD_AXIS_LEFT_X)
    input.y += rl.get_gamepad_axis_movement(0, rl.GAMEPAD_AXIS_LEFT_Y)

    util.debug_draw_input_axis(input)

    if (vec_length := glm.length(input)) > 1:
        input /= vec_length

    state.player += input


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
