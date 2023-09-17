from dataclasses import dataclass
import pyray as rl
import glm
import json

TILE_SIZE = 16

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

# size_spring = Spring(70, 4, 0)

def tile_rect(point):
    return rl.Rectangle(int(point[0] * TILE_SIZE), int(point[1] * TILE_SIZE), TILE_SIZE, TILE_SIZE)

def normalize0(v):
    return glm.normalize(v) if v != glm.vec2() else glm.vec2()

def fix_map_overlap(collision_mask, actor_pos):
    '''Fix overlap with map tiles. Mutates `actor_pos`.'''
    collided = False
    for i in range(3):
        overlap = glm.vec2()
        most_area = 0
        for dir in [(0, 0), (1, 0),
                    (0, 1), (1, 1)]:
            tile = glm.ivec2(actor_pos + dir)
            if 0 <= tile.y < len(collision_mask) and 0 <= tile.x < len(collision_mask[0]) and collision_mask[tile.y][tile.x]:
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
        if overlap != glm.vec2():
            collided = True
        actor_pos += overlap
    return collided

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

class Grid:
    def __init__(self, tiles):
        self.tiles = tiles

    def __getitem__(self, pos):
        if pos in self:
            return self.tiles[pos[1]][pos[0]]
        return None

    def __setitem__(self, pos, val):
        if pos in self:
            self.tiles[pos[1]][pos[0]] = val

    def __contains__(self, pos):
        return (0 <= pos[0] < len(self.tiles[0]) and
                0 <= pos[1] < len(self.tiles))

    def __iter__(self):
        """Iterate over rows."""
        yield from iter(self.tiles)

    def __len__(self):
        """Return the number of rows."""
        return len(self.tiles)

@dataclass
class Enemy:
    pos: glm.vec2
    path: list[glm.ivec2]

def load_map(path):
    with open(path, 'r') as f:
        d = json.load(f)
        return load_map_data(d)

def load_map_data(data):
    enemies = [Enemy(glm.vec2(*p), []) for p in data['enemy_pos']]
    layers = [Grid(tiles) for tiles in data['layers']]
    trigger_tags = {}
    for k, v in data['trigger_tags'].items():
        x, y = k.split()
        trigger_tags[(int(x), int(y))] = v
    return layers, enemies, trigger_tags, glm.vec2(data['spawn'])
