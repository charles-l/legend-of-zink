from dataclasses import dataclass

# https://github.com/electronstudio/raylib-python-cffi
import pyray as rl
import glm
import random
from util import *

WIDTH = 800
HEIGHT = 600

rl.init_window(WIDTH, HEIGHT, "Legend of Zink")
rl.init_audio_device()
rl.set_target_fps(60)

# load resources
music = rl.load_music_stream("demoassets/bg1.xm")
throw_sfx = rl.load_sound("demoassets/throw.wav")
hit_sfx = rl.load_sound("demoassets/hit.wav")
rl.play_music_stream(music)

sword_tex = rl.load_texture("demoassets/sword.png")
zink_tex = rl.load_texture("demoassets/zink.png")
enemy_tex = rl.load_texture("demoassets/enemy.png")
run_frames = {
    (0, -1): list(range(0, 4)),
    (1, 0): list(range(4, 8)),
    (0, 1): list(range(8, 12)),
    (-1, 0): list(range(12, 16)),
}


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


@dataclass
class Player:
    pos: glm.vec2 = glm.vec2()
    heading: glm.vec2 = glm.vec2(0, 1)
    frame: int = 0


sword = Sword(glm.vec2(), glm.vec2())
player = Player()

tileset_tex = rl.load_texture("demoassets/tileset.png")
with open("demoassets/tileset.def.json") as f:
    tilesetdef = json.load(f)

debug_rects = []
frame_i = 0


class Scene:
    def __init__(self, mapfile):
        self.map_layers, self.enemies, self.trigger_tags, player.pos = load_map(mapfile)
        self.collision_map = [
            [tilesetdef[t]["collision"] == "collide" for t in row]
            for row in self.map_layers[0]
        ]

    def handle_collisions(self, actor_pos):
        nearby_tiles = []
        for dir in [(0, 0), (1, 0), (0, 1), (1, 1)]:
            tile = glm.ivec2(actor_pos + dir)
            if self.collision_map[tile.y][tile.x]:
                nearby_tiles.append(tile_rect(tile))

        if new_pos := resolve_map_collision(nearby_tiles, tile_rect(actor_pos)):
            actor_pos.x, actor_pos.y = new_pos.x / TILE_SIZE, new_pos.y / TILE_SIZE
            return True
        else:
            return False


scene = Scene("demoassets/map.json")

fade_out_rect = 0
event_queue = []


def fade_to(inner_co):
    global fade_out_rect
    start = rl.get_time()
    while rl.get_time() - start < 0.1:
        fade_out_rect = (rl.get_time() - start) / 0.1
        yield

    fade_out_rect = 1

    yield from inner_co

    start = rl.get_time()
    while rl.get_time() - start < 0.1:
        fade_out_rect = 1 - ((rl.get_time() - start) / 0.1)
        yield

    fade_out_rect = 0


def load_scene(mapfile):
    global scene
    scene = Scene(mapfile)
    print("load scene", mapfile)
    yield


# set up camera
camera = rl.Camera2D()
camera.zoom = 6
camera.offset = WIDTH / 2, HEIGHT / 2
# rl.toggle_fullscreen()
while not rl.window_should_close():
    frame_i += 1
    debug_rects.clear()
    rl.update_music_stream(music)
    if event_queue:
        try:
            next(event_queue[0])
        except StopIteration:
            event_queue.pop(0)

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
        rl.set_sound_pitch(throw_sfx, 1 + random.uniform(-0.1, 0.1))
        rl.play_sound(throw_sfx)
        sword.pos = glm.vec2(player.pos)
        sword.vel = glm.vec2(player.heading) * 0.3

    if input_dir != glm.vec2():
        if abs(input_dir.x) > abs(input_dir.y):
            player.heading = glm.vec2(glm.sign(input_dir.x), 0)
        else:
            player.heading = glm.vec2(0, glm.sign(input_dir.y))

        player.frame = run_frames[(int(player.heading.x), int(player.heading.y))][
            int((rl.get_time() % 0.4) / 0.1)
        ]

    player.pos += 0.07 * normalize0(input_dir)

    sword.pos += sword.vel

    camera_follow_window(camera, player.pos * TILE_SIZE, 40, 40)

    for e in scene.enemies:
        e.pos.x += 0.04 if rl.get_time() % 4 < 2 else -0.04

    # collisions
    for t, v in scene.trigger_tags.items():
        if (
            rl.check_collision_recs(tile_rect(t), tile_rect(player.pos))
            and not event_queue
        ):
            print("trigger", v)
            event_queue.append(fade_to(load_scene("demoassets/cave.json")))
            music = rl.load_music_stream("demoassets/cave.xm")
            rl.play_music_stream(music)

    if sword.is_active():
        collided = False
        if scene.handle_collisions(sword.pos):
            collided = True
        to_kill = []
        for i, e in enumerate(scene.enemies):
            if rl.check_collision_recs(tile_rect(sword.pos), tile_rect(e.pos)):
                rl.play_sound(hit_sfx)
                to_kill.append(i)
                collided = True
        for i in reversed(to_kill):
            del scene.enemies[i]
        if collided:
            sword.deactivate()

    scene.handle_collisions(player.pos)
    for e in scene.enemies:
        scene.handle_collisions(e.pos)
        if (
            rl.check_collision_recs(tile_rect(player.pos), tile_rect(e.pos))
            and last_damage.trigger()
        ):
            print("damage")

    ### drawing
    rl.begin_drawing()
    rl.begin_mode_2d(camera)
    rl.clear_background(rl.LIGHTGRAY)

    for y, row in enumerate(scene.map_layers[0]):
        for x, c in enumerate(row):
            if c != 0:
                rl.draw_texture_pro(
                    tileset_tex,
                    rl.Rectangle(*tilesetdef[c]["rect"]),
                    itile_rect(glm.vec2(x, y)),
                    (0, 0),
                    0,
                    rl.WHITE,
                )
                # rl.draw_rectangle(int(x * TILE_SIZE), int(y * TILE_SIZE), TILE_SIZE, TILE_SIZE, rl.GRAY)

    for e in scene.enemies:
        frame = rl.get_time() % 0.2 // 0.1
        rl.draw_texture_pro(
            enemy_tex,
            rl.Rectangle(frame * TILE_SIZE, 0, TILE_SIZE, TILE_SIZE),
            itile_rect(e.pos),
            (0, 0),
            0,
            rl.WHITE,
        )

    color = rl.WHITE
    if last_damage.cooldown_active() and last_damage.cooldown_time % 0.2 < 0.1:
        color = rl.RED
    # rl.draw_rectangle_lines(int(player.pos.x * TILE_SIZE), int(player.pos.y * TILE_SIZE), TILE_SIZE, TILE_SIZE, color)
    rl.draw_texture_pro(
        zink_tex,
        rl.Rectangle(player.frame * TILE_SIZE, 0, TILE_SIZE, TILE_SIZE),
        itile_rect(player.pos),
        (0, 0),
        0,
        color,
    )
    # rl.draw_line_v(tuple(player.pos * TILE_SIZE + TILE_SIZE / 2), tuple(player.pos * TILE_SIZE + player.heading * TILE_SIZE * 1.5 + TILE_SIZE / 2), rl.GREEN)

    if sword.is_active():
        sword_heading = glm.ivec2(glm.normalize(sword.vel)).to_tuple()
        angle = {(0, -1): 0, (1, 0): 90, (0, 1): 180, (-1, 0): 270}[sword_heading]
        rl.draw_texture_pro(
            sword_tex,
            itile_rect(glm.vec2(0, 0)),
            itile_rect(sword.pos + (0.5, 0.5)),
            (TILE_SIZE // 2, TILE_SIZE // 2),
            angle,
            rl.WHITE,
        )
        # rl.draw_rectangle(int(sword.pos.x * TILE_SIZE), int(sword.pos.y * TILE_SIZE), TILE_SIZE, TILE_SIZE, rl.PURPLE)

    for r in debug_rects:
        rl.draw_rectangle_lines(
            int(r.x), int(r.y), int(r.width), int(r.height), rl.PURPLE
        )

    rl.end_mode_2d()

    if fade_out_rect:
        rl.draw_rectangle(0, 0, WIDTH, HEIGHT, rl.fade(rl.BLACK, fade_out_rect))

    rl.end_drawing()
