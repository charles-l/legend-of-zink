from dataclasses import dataclass
import random
import pyray as rl
import glm

@dataclass
class Spring:
    k: float
    damping: float
    value: float
    v: float = 0

    def update(self, target_value, dt=None):
        springforce = -self.k*(self.value-target_value)
        damp = self.damping * self.v
        force = springforce - damp
        if dt is None:
            dt = rl.get_frame_time()
        self.v += force * dt
        self.value += self.v * dt
        return self.value

size_spring = Spring(70, 4, 0)

WIDTH = 800
HEIGHT = 600

rl.init_window(WIDTH, HEIGHT, "game")
rl.set_target_fps(60)

TILE_SIZE = 16

bg_map = '''\
......x.....x...
............x...
......x.....x...
......x.....x...
xxxxxxx.....x...
................
................
................
..........x.x...
..........x.x...
..........x.x...
..........x.x...
..........x.x...
................
................
................'''.split('\n')

player_pos = glm.vec2(3, 3)
enemy_pos = [glm.vec2(5, 6)]

def tile_rect(point):
    return rl.Rectangle(point.x * TILE_SIZE, point.y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

def normalize0(v):
    return glm.normalize(v) if v != glm.vec2() else glm.vec2()

def fix_map_overlap(actor_pos):
    '''Fix overlap with map tiles. Mutates `actor_pos`.'''
    # TODO: handle bounds properly
    for i in range(3):
        overlap = glm.vec2()
        most_area = 0
        for dir in [(0, 0), (1, 0),
                    (0, 1), (1, 1)]:
            tile = glm.ivec2(actor_pos + dir)
            if bg_map[tile.y][tile.x] == 'x':
                overlap_rec = rl.get_collision_rec(tile_rect(tile), tile_rect(actor_pos))
                overlap_area = overlap_rec.width * overlap_rec.height
                if overlap_area > most_area:
                    most_area = overlap_area
                    if overlap_rec.width < overlap_rec.height:
                        dir = -1 if actor_pos.x < tile.x else 1
                        overlap = glm.vec2(dir * overlap_rec.width / TILE_SIZE, 0)
                    else:
                        dir = -1 if actor_pos.y < tile.y else 1
                        overlap = glm.vec2(0, dir * overlap_rec.height / TILE_SIZE)
        actor_pos += overlap

class CooldownTimer:
    def __init__(self, cooldown):
        self.last_time = float('-inf')
        self.cooldown = cooldown

    @property
    def cooldown_time(self):
        return rl.get_time() - self.last_time

    def cooldown_active(self):
        return self.cooldown_time <= self.cooldown

    def trigger(self):
        if not self.cooldown_active():
            self.last_time = rl.get_time()
            return True
        else:
            return False

last_damage = CooldownTimer(2)
heading = glm.vec2(0, 1)

# set up camera
camera = rl.Camera2D()
camera.offset = 0, 0
camera.zoom = 3
while not rl.window_should_close():
    ### drawing
    rl.begin_drawing()
    rl.begin_mode_2d(camera)
    rl.clear_background(rl.LIGHTGRAY)

    input_dir = glm.vec2()
    if rl.is_key_down(rl.KEY_LEFT):
        input_dir.x -= 1
    if rl.is_key_down(rl.KEY_RIGHT):
        input_dir.x += 1
    if rl.is_key_down(rl.KEY_UP):
        input_dir.y -= 1
    if rl.is_key_down(rl.KEY_DOWN):
        input_dir.y += 1

    if input_dir != glm.vec2():
        if abs(input_dir.x) > abs(input_dir.y):
            heading = glm.vec2(glm.sign(input_dir.x), 0)
        else:
            heading = glm.vec2(0, glm.sign(input_dir.y))

    player_pos += 0.1 * normalize0(input_dir)

    # collisions
    fix_map_overlap(player_pos)
    for e in enemy_pos:
        if rl.check_collision_recs(tile_rect(player_pos), tile_rect(e)) and last_damage.trigger():
            print('damage')

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

    rl.end_mode_2d()
    rl.end_drawing()
