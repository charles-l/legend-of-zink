from dataclasses import dataclass
import pyray as rl
import glm
from util import *

WIDTH = 800
HEIGHT = 600

rl.init_window(WIDTH, HEIGHT, "game")
rl.set_target_fps(60)

bg_map = '''\
......x.....x........
............x........
......x.....x........
......x.....x........
xxxxxxx.....x........
.....................
................x....
................x....
..........x.x...x....
..........x.x........
..........x.x........
..........x.x........
..........x.x........
.....................
.....................
.....................'''.split('\n')

player_pos = glm.vec2(3, 3)
enemy_pos = [glm.vec2(5, 6)]

@dataclass
class Sword:
    pos: glm.vec2
    vel: glm.vec2

    def is_active(self):
        return self.vel != glm.vec2()

    def deactivate(self):
        self.vel = glm.vec2()

last_damage = CooldownTimer(2)
heading = glm.vec2(0, 1)

sword = Sword(glm.vec2(), glm.vec2())

# set up camera
camera = rl.Camera2D()
camera.zoom = 3
camera.offset = WIDTH / 2, HEIGHT / 2
while not rl.window_should_close():
    input_dir = glm.vec2()
    if rl.is_key_down(rl.KEY_LEFT):
        input_dir.x -= 1
    if rl.is_key_down(rl.KEY_RIGHT):
        input_dir.x += 1
    if rl.is_key_down(rl.KEY_UP):
        input_dir.y -= 1
    if rl.is_key_down(rl.KEY_DOWN):
        input_dir.y += 1
    if rl.is_key_released(rl.KEY_SPACE):
        sword.pos = glm.vec2(player_pos)
        sword.vel = glm.vec2(heading) * 0.5

    if input_dir != glm.vec2():
        if abs(input_dir.x) > abs(input_dir.y):
            heading = glm.vec2(glm.sign(input_dir.x), 0)
        else:
            heading = glm.vec2(0, glm.sign(input_dir.y))

    player_pos += 0.1 * normalize0(input_dir)

    sword.pos += sword.vel

    errx = glm.clamp(camera.target.x - player_pos.x * TILE_SIZE, -20, 20)
    erry = glm.clamp(camera.target.y - player_pos.y * TILE_SIZE, -20, 20)
    camera.target.x = errx + player_pos.x * TILE_SIZE
    camera.target.y = erry + player_pos.y * TILE_SIZE

    # collisions
    if sword.is_active():
        collided = False
        if fix_map_overlap(bg_map, sword.pos):
            collided = True
        to_kill = []
        for i, e in enumerate(enemy_pos):
            if rl.check_collision_recs(tile_rect(sword.pos), tile_rect(e)):
                to_kill.append(i)
                collided = True
        for i in reversed(to_kill):
            del enemy_pos[i]
        if collided:
            sword.deactivate()

    fix_map_overlap(bg_map, player_pos)
    for e in enemy_pos:
        if rl.check_collision_recs(tile_rect(player_pos), tile_rect(e)) and last_damage.trigger():
            print('damage')

    ### drawing
    rl.begin_drawing()
    rl.begin_mode_2d(camera)
    rl.clear_background(rl.LIGHTGRAY)

    for y, row in enumerate(bg_map):
        for x, c in enumerate(row):
            if c == '.':
                pass
                #rl.draw_rectangle_lines(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE, rl.GREEN)
            elif c == 'x':
                rl.draw_rectangle(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE, rl.GRAY)

    for e in enemy_pos:
        rl.draw_rectangle(int(e.x * TILE_SIZE), int(e.y * TILE_SIZE), TILE_SIZE, TILE_SIZE, rl.RED)

    color = rl.GREEN
    if last_damage.cooldown_active() and last_damage.cooldown_time % 0.2 < 0.1:
        color = rl.WHITE
    rl.draw_rectangle(int(player_pos.x * TILE_SIZE), int(player_pos.y * TILE_SIZE), TILE_SIZE, TILE_SIZE, color)
    rl.draw_line_v(tuple(player_pos * TILE_SIZE + TILE_SIZE / 2), tuple(player_pos * TILE_SIZE + heading * TILE_SIZE * 1.5 + TILE_SIZE / 2), rl.GREEN)

    if sword.is_active():
        rl.draw_rectangle(int(sword.pos.x * TILE_SIZE), int(sword.pos.y * TILE_SIZE), TILE_SIZE, TILE_SIZE, rl.PURPLE)

    rl.end_mode_2d()
    rl.end_drawing()
