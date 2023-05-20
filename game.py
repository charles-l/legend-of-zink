# undertale-like gameplay?
from dataclasses import dataclass
import pyray as rl
import glm

TILE_SIZE = 30

map = [
    '.......................',
    '.                     .',
    '.                     .',
    '.    ...              .',
    '.                     .',
    '.                     .',
    '.                     .',
    '.                     .',
    '.                     .',
    '.                     .',
    '.                     .',
    '.                     .',
    '.......................',
]

@dataclass
class Player:
    x: float
    y: float

player = rl.Rectangle(1, 1, 1, 1)

rl.init_window(800, 600, "game")
rl.set_target_fps(60)
while not rl.window_should_close():
    ### input/logic
    vel = glm.vec2(0, 0)
    if rl.is_key_down(rl.KEY_LEFT):
        vel.x -= 1
    if rl.is_key_down(rl.KEY_RIGHT):
        vel.x += 1
    if rl.is_key_down(rl.KEY_DOWN):
        vel.y += 1
    if rl.is_key_down(rl.KEY_UP):
        vel.y -= 1

    if glm.length(vel) > 0:
        vel = glm.normalize(vel) * 0.1

    #player_center = glm.vec2(player.x, player.y) + glm.vec2(TILE_SIZE // 2)

    player.x += vel.x
    player.y += vel.y

    corners = [(0, 0), (0, 1), (1, 0), (1, 1)]
    print([map[int(player.y) + cy][int(player.x) + cx] == '.' for cx, cy in corners])

    ### drawing
    rl.begin_drawing()
    rl.clear_background(rl.GRAY)
    for y, row in enumerate(map):
        for x, tile in enumerate(row):
            if tile == '.':
                rl.draw_rectangle(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE, rl.WHITE)
    rl.draw_rectangle(int(player.x * TILE_SIZE), int(player.y * TILE_SIZE), int(player.width * TILE_SIZE), int(player.height * TILE_SIZE), rl.GREEN)
    rl.end_drawing()
