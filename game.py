import pyray as rl, glm, util
from types import SimpleNamespace

WIDTH, HEIGHT = 800, 600

PLAYER_SIZE = 100

rl.init_window(WIDTH, HEIGHT, "My awesome game")

state = SimpleNamespace(
    player=glm.vec2(10, 10),
    walls=[
        rl.Rectangle(300, 0, 10, 400),
        rl.Rectangle(0, 500, 400, 10),
    ],
)


camera = rl.Camera2D(
    (WIDTH / 2, HEIGHT / 2), (0, 0), 0, 1  # offset from target  # target  # rotation
)  # zoom


def update(state):
    input = glm.vec2()
    if rl.is_key_down(rl.KEY_DOWN):
        input.y += 1
    if rl.is_key_down(rl.KEY_UP):
        input.y -= 1
    if rl.is_key_down(rl.KEY_LEFT):
        input.x -= 1
    if rl.is_key_down(rl.KEY_RIGHT):
        input.x += 1

    input.x += rl.get_gamepad_axis_movement(0, rl.GAMEPAD_AXIS_LEFT_X)
    input.y += rl.get_gamepad_axis_movement(0, rl.GAMEPAD_AXIS_LEFT_Y)

    util.debug_draw_input_axis(input)

    if (vec_length := glm.length(input)) > 1:
        input /= vec_length

    state.player += input * 4

    player_rect = rl.Rectangle(state.player.x, state.player.y, PLAYER_SIZE, PLAYER_SIZE)

    new_pos = util.resolve_map_collision(state.walls, player_rect)
    if new_pos is not None:
        state.player.x, state.player.y = new_pos.x, new_pos.y


def draw(state):
    rl.clear_background(rl.BLACK)
    rl.begin_mode_2d(camera)
    util.camera_follow_window(
        camera, state.player + (PLAYER_SIZE / 2, PLAYER_SIZE / 2), 100, 100
    )
    rl.draw_rectangle(
        int(state.player.x), int(state.player.y), PLAYER_SIZE, PLAYER_SIZE, rl.RED
    )
    for wall in state.walls:
        rl.draw_rectangle_rec(wall, rl.WHITE)
    rl.end_mode_2d()
    util.debug_draw_camera_follow_window(100 + PLAYER_SIZE, 100 + PLAYER_SIZE)


rl.set_target_fps(60)
while not rl.window_should_close():
    update(state)
    rl.begin_drawing()
    rl.draw_fps(10, 10)
    draw(state)
    rl.end_drawing()
