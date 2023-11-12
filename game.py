import pyray as rl, glm, util
from types import SimpleNamespace
import random

WIDTH, HEIGHT = 800, 600

PLAYER_SIZE = 100

rl.init_window(WIDTH, HEIGHT, "My awesome game")
rl.init_audio_device()

music = rl.load_music_stream("demoassets/bg1.xm")
rl.set_music_volume(music, 0.3)
rl.play_music_stream(music)

step = rl.load_sound("demoassets/step.wav")

state = SimpleNamespace(
    player=glm.vec2(10, 10),
    walls=[
        rl.Rectangle(100, -40, 10, 400),
        rl.Rectangle(-200, 400, 400, 10),
    ],
)

camera = rl.Camera2D(
    (WIDTH / 2, HEIGHT / 2), (0, 0), 0, 2  # offset from target  # target  # rotation
)  # zoom

player_tex = rl.load_texture("demoassets/zink.png")
PLAYER_SIZE = 16
PLAYER_FRAMES = [4, 5, 6, 7]


def update(state):
    rl.update_music_stream(music)
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

    last_step_i = int(((rl.get_time() - rl.get_frame_time()) * 10) % 4)
    step_i = int((rl.get_time() * 10) % 4)
    if last_step_i != step_i and step_i in (1, 3):
        rl.set_sound_pitch(step, random.uniform(0.7, 1.4))
        rl.play_sound(step)
    current_frame = PLAYER_FRAMES[step_i]
    rl.draw_texture_pro(
        player_tex,
        rl.Rectangle(PLAYER_SIZE * current_frame, 0, PLAYER_SIZE, PLAYER_SIZE),
        rl.Rectangle(state.player.x, state.player.y, PLAYER_SIZE, PLAYER_SIZE),
        (0, 0),
        0,
        rl.WHITE,
    )

    for wall in state.walls:
        rl.draw_rectangle_rec(wall, rl.WHITE)

    rl.end_mode_2d()


def menu_step():
    global step_frame_func
    rl.begin_drawing()
    rl.draw_text("LEGEND OF ZINK", 30, 30, 50, rl.WHITE)
    if rl.gui_button(rl.Rectangle(30, 90, 100, 50), "START") or rl.is_key_released(
        rl.KEY_SPACE
    ):
        step_frame_func = game_step
    rl.end_drawing()


def game_step():
    update(state)
    rl.begin_drawing()
    rl.draw_fps(10, 10)
    draw(state)
    rl.end_drawing()


step_frame_func = menu_step
try:
    rl.set_target_fps(60)
    while not rl.window_should_close():
        step_frame_func()
finally:
    rl.close_audio_device()
