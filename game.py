# jousting
from dataclasses import dataclass
import random
import pyray as rl
import glm

@dataclass
class Player:
    pos: glm.vec2
    size: float

WIDTH, HEIGHT = 2400, 1000

state = {
    'players': [Player(glm.vec2(0, 0), 20), Player(glm.vec2(400, 10), 10)],
    'pellets': [],
}

rl.init_window(WIDTH, HEIGHT, "game")
rl.set_target_fps(60)

PELLET_SIZE = 4

# spawn pellets
for i in range(100):
    state['pellets'].append((random.randint(0, WIDTH), random.randint(0, HEIGHT)))

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

# set up camera
camera = rl.Camera2D()
camera.offset = WIDTH / 2, HEIGHT / 2
camera.zoom = 2
while not rl.window_should_close():
    player = state['players'][0]
    mouse_pos = rl.get_screen_to_world_2d(rl.get_mouse_position(), camera)
    move_diff = glm.vec2(mouse_pos.x, mouse_pos.y) - player.pos
    speed = 5
    diff_len = glm.length(move_diff)
    if diff_len > speed:
        move_diff /= glm.length(diff_len)
        move_diff *= speed
    player.pos += move_diff

    if glm.distance((camera.target.x, camera.target.y), player.pos) > 100:
        g = player.pos + glm.normalize((camera.target.x, camera.target.y) - player.pos) * 100
        camera.target = (int(g[0]), int(g[1]))

    pellets_to_delete = set()
    for i, (px, py) in enumerate(state['pellets']):
        if glm.distance((px, py), player.pos) < PELLET_SIZE + player.size:
            player.size += 0.5
            size_spring.value += 5
            pellets_to_delete.add(i)
    state['pellets'] = [x for i, x in enumerate(state['pellets']) if i not in pellets_to_delete]

    # handle eating other players
    for i, p in enumerate(state['players']):
        if p == player:
            continue
        p.pos += glm.normalize((random.choice([-1, 1]) * 5, random.choice([-1, 1]) * 5))
        if glm.distance(p.pos, player.pos) < player.size + p.size:
            if player.size < p.size:
                state['players'][0].size = 0
            else:
                state['players'][i].size = 0

    ### drawing
    rl.begin_drawing()
    rl.begin_mode_2d(camera)
    rl.clear_background(rl.LIGHTGRAY)
    for px, py in state['pellets']:
        rl.draw_circle(px, py, PELLET_SIZE, rl.BLUE)
    for p in state['players']:
        if p == player:
            rl.draw_circle(int(p.pos.x), int(p.pos.y), size_spring.update(p.size), rl.GREEN)
            rl.draw_circle_lines(int(p.pos.x), int(p.pos.y), p.size, rl.DARKGREEN)
        else:
            rl.draw_circle(int(p.pos.x), int(p.pos.y), p.size, rl.RED)
    rl.end_mode_2d()
    rl.end_drawing()
