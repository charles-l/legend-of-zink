from dataclasses import dataclass
import pyray as rl
import glm
import json
from typing import Optional

TILE_SIZE = 16


@dataclass
class Spring:
    k: float
    damping: float
    value: float
    v: float = 0

    def update(self, target_value, dt=None):
        springforce = -self.k * (self.value - target_value)
        damp = self.damping * self.v
        force = springforce - damp
        if dt is None:
            dt = rl.get_frame_time()
        self.v += force * dt
        self.value += self.v * dt
        return self.value


# size_spring = Spring(70, 4, 0)


def tile_rect(point):
    return rl.Rectangle(
        point[0] * TILE_SIZE, point[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE
    )


def itile_rect(point):
    return rl.Rectangle(
        int(point[0] * TILE_SIZE), int(point[1] * TILE_SIZE), TILE_SIZE, TILE_SIZE
    )


def normalize0(v):
    return glm.normalize(v) if v != glm.vec2() else glm.vec2()


def camera_follow_window(camera, target_pos, window_width, window_height):
    target_pos = target_pos
    window_width = window_width / camera.zoom
    window_height = window_height / camera.zoom
    errx = glm.clamp(
        camera.target.x - target_pos.x, -window_width / 2, window_width / 2
    )
    erry = glm.clamp(
        camera.target.y - target_pos.y, -window_height / 2, window_height / 2
    )
    camera.target.x = errx + target_pos.x
    camera.target.y = erry + target_pos.y


def copy_rect(rect):
    return rl.Rectangle(rect.x, rect.y, rect.width, rect.height)


def get_signed_collision_rec(rect1: rl.Rectangle, rect2: rl.Rectangle) -> rl.Rectangle:
    """Compute the rectangle of intersection between rect1 and rect2.

    If rect2 is to the left or above rect1, the width or height will
    be flipped, respectively."""
    r = rl.get_collision_rec(rect1, rect2)
    if rect2.x < rect1.x:
        r.width = -r.width
    if rect2.y < rect1.y:
        r.height = -r.height
    return r


def resolve_map_collision(map_aabbs, actor_aabb) -> Optional[glm.vec2]:
    """Fix overlap with map tiles. Returns new position for actor_aabb."""
    # internal copy of actor_aabb that will be mutated
    aabb = copy_rect(actor_aabb)
    if map_aabbs:
        for i in range(3):  # run multiple iters to handle corners/passages
            most_overlap = max(
                (get_signed_collision_rec(r, aabb) for r in map_aabbs),
                key=lambda x: abs(x.width * x.height),
            )
            if abs(most_overlap.width) < abs(most_overlap.height):
                aabb.x += most_overlap.width
            else:
                aabb.y += most_overlap.height

    new_pos = glm.vec2(aabb.x, aabb.y)
    old_pos = (actor_aabb.x, actor_aabb.y)
    return new_pos if new_pos != old_pos else None


class CooldownTimer:
    def __init__(self, cooldown):
        self.last_time = float("-inf")
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
        return 0 <= pos[0] < len(self.tiles[0]) and 0 <= pos[1] < len(self.tiles)

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
    with open(path, "r") as f:
        d = json.load(f)
        return load_map_data(d)


def load_map_data(data):
    enemies = [Enemy(glm.vec2(*p), []) for p in data["enemy_pos"]]
    layers = [Grid(tiles) for tiles in data["layers"]]
    trigger_tags = {}
    for k, v in data["trigger_tags"].items():
        x, y = k.split()
        trigger_tags[(int(x), int(y))] = v
    return layers, enemies, trigger_tags, glm.vec2(data["spawn"])


def debug_draw_input_axis(input_vec, x=400, y=100):
    rl.draw_circle_lines(x, y, 50, rl.GRAY)
    rl.draw_line(x, y, int(x + input_vec.x * 50), int(y + input_vec.y * 50), rl.RED)

    clamped = glm.vec2(input_vec.x, input_vec.y)
    if (vlen := glm.length(clamped)) > 1:
        clamped /= vlen
    rl.draw_line(x, y, int(x + clamped.x * 50), int(y + clamped.y * 50), rl.GREEN)


def debug_draw_camera_follow_window(width, height):
    centerx = rl.get_screen_width() / 2
    centery = rl.get_screen_height() / 2
    rl.draw_rectangle_lines(
        int(centerx - width / 2), int(centery - height / 2), width, height, rl.PURPLE
    )
