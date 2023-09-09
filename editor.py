from dataclasses import dataclass
import pyray as rl
import glm
import random
import timeit
import json
import pathlib
import pickle
import collections
import contextlib
from util import *
from typing import Literal, Union

WIDTH = 1600
HEIGHT = 1200

class Tileset:
    @staticmethod
    def load_tiles(path):
        tiles = {}
        with open(path, 'r') as f:
            tiles = json.load(f)
        tex = rl.load_texture(path.replace('.def.json', '.png'))
        for tile in tiles:
            if any(x not in tile for x in ['rect', 'collision']):
                raise Exception("Data doesn't match schema", tile)
            tile['rect'] = rl.Rectangle(*tile['rect'])
        return tiles, tex

    def __init__(self, path):
        self.path = path
        self.tiles, self.tex = self.load_tiles(path)

    def set(self, i, property, value):
        self.tiles[i][property] = value
        output = []
        # hacked up deepcopy (just for self.tiles) because copy.deepcopy
        # doesn't work with CFFI objects because they can't be pickled. ugh.
        for old_t in self.tiles:
            t = dict(old_t)
            r = t['rect']
            t['rect'] = [r.x, r.y, r.width, r.height]
            output.append(t)

        with open(self.path, 'w') as f:
            json.dump(output, f)

    def draw_tile(self, i, target_rect):
        rl.draw_texture_pro(self.tex,
                            self.tiles[i]['rect'],
                            target_rect,
                            (0, 0),
                            0,
                            rl.WHITE)

class EditHistory:
    def __init__(self):
        self.undo_stack = collections.deque(maxlen=10)
        self.undo_pos = -1
        self.level_hash = 0
        self.last_save_hash = 0
        self.serialized_map = {}

    def save_current(self, output_file):
        if self.last_save_hash != self.level_hash:
            print('saving')
            with open(output_file, 'w') as f:
                json.dump(self.serialized_map, f)
            self.last_save_hash = self.level_hash

    def update(self, map):
        self.serialized_map = map.serialize()
        pickled_map = pickle.dumps(self.serialized_map)
        new_hash = hash(pickled_map)
        # add to undo history
        if new_hash != self.level_hash:
            if self.undo_pos != -1:
                # squash undo traversal to history and apply change
                # https://github.com/zaboople/klonk/blob/master/TheGURQ.md
                self.undo_stack.extend(reversed(list(self.undo_stack)[self.undo_pos:-1]))
            self.undo_stack.append(pickled_map)
            self.undo_pos = -1
            self.level_hash = new_hash

    def step_history(self, dir: Literal[1, -1], map):
        self.undo_pos += dir
        self.undo_pos = glm.clamp(self.undo_pos, -len(self.undo_stack), -1)
        data = pickle.loads(self.undo_stack[self.undo_pos])
        map.layers, map.enemies, map.spawn = load_map_data(data)
        self.level_hash = hash(self.undo_stack[self.undo_pos])
        return data

def crop(tiles, width, height):
    return [row[:width] for row in tiles[:height]]

class Map:
    def __init__(self, mappath):
        if mappath is None:
            self.enemies = []
            self.layers = [Grid([[0] * MAX_TILES for _ in range(MAX_TILES)]) for _ in range(2)]
            self.spawn = glm.vec2(-1, -1)
        else:
            self.layers, self.enemies, self.spawn = load_map(mappath)
            width_ptr[0] = len(self.layers[0].tiles[0])
            height_ptr[0] = len(self.layers[0].tiles)
            # Resize each layer to be MAX_TILES by MAX_TILES so we can always
            # assume we have that many tiles available.
            for i in range(len(self.layers)):
                self.layers[i].tiles = [
                    row + [0] * (MAX_TILES - len(row)) for row in self.layers[i]
                    ] + [[0] * MAX_TILES for _ in range(MAX_TILES - len(self.layers[i]))]

    def serialize(self):
        return {'layers': [crop(l.tiles, width_ptr[0], height_ptr[0]) for l in self.layers],
                'enemy_pos': [e.pos.to_tuple() for e in self.enemies],
                'spawn': self.spawn.to_tuple()}

    @property
    def bg(self):
        return self.layers[0]

    @property
    def fg(self):
        return self.layers[1]

# track y offset to simplify creating rows in the GUI
@dataclass
class YLayout:
    yoff: float = 5
    padding: float = 5

    @contextlib.contextmanager
    def row(self, height):
        yield self.yoff
        self.yoff += height + self.padding

def flood_fill(tiles, pos, new_tile):
    old_tile = tiles[pos]
    if old_tile == new_tile:
        return
    queue = [pos]
    while queue:
        x, y = queue.pop()
        tiles[x, y] = new_tile
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            if (x + dx, y + dy) in tiles and tiles[x + dx, y + dy] == old_tile:
                queue.append((x+dx, y+dy))

###

rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
rl.init_window(WIDTH, HEIGHT, "Legend of Zink [EDITOR]")
rl.init_audio_device()
rl.set_target_fps(60)

tileset = Tileset("tileset.def.json")
enemy_tex = rl.load_texture('enemy.png')
zink_tex = rl.load_texture('zink.png')

camera = rl.Camera2D()
camera.zoom = 1
camera.offset = WIDTH / 2, HEIGHT / 2

width_edit_mode = False
width_ptr = rl.ffi.new("int *")
width_ptr[0] = 40

height_edit_mode = False
height_ptr = rl.ffi.new("int *")
height_ptr[0] = 40

@dataclass
class TileEditState:
    selected_tile: int = 1

@dataclass
class EnemyEditState:
    selected_enemy: int = 0

@dataclass
class SpawnEditState:
    pass

editor_state: Union[TileEditState, EnemyEditState, SpawnEditState] = TileEditState()
selected_layer = 0

MAX_TILES = 40
# larger tiles for display on hidpi machines
ZOOM_TILE_SIZE = TILE_SIZE * 4
COLLISION_TYPES = "none trigger collide".split()

mapfile = pathlib.Path('map.json')
if mapfile.exists():
    map = Map(mapfile)
else:
    map = Map(None)

edit_history = EditHistory()
edit_history.update(map)
last_autosave = 0

number_keys = 'ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE'.split()
while not rl.window_should_close():
    if rl.is_key_pressed(rl.KEY_Z) and rl.is_key_down(rl.KEY_LEFT_CONTROL):
        edit_history.step_history(-1, map)
    if rl.is_key_pressed(rl.KEY_Y) and rl.is_key_down(rl.KEY_LEFT_CONTROL):
        edit_history.step_history(1, map)

    for i, s in enumerate(number_keys):
        if rl.is_key_released(getattr(rl, f'KEY_{s}')) and 0 <= i < len(tileset.tiles):
            editor_state = TileEditState(i)
    if rl.is_key_released(rl.KEY_E):
        editor_state = EnemyEditState()
    if rl.is_key_released(rl.KEY_S):
        editor_state = SpawnEditState()


    if rl.is_mouse_button_down(rl.MOUSE_BUTTON_RIGHT):
        camera.target.x -= rl.get_mouse_delta().x
        camera.target.y -= rl.get_mouse_delta().y

    camera.zoom += rl.get_mouse_wheel_move()
    camera.zoom = glm.clamp(camera.zoom, 0.5, 10)

    rl.begin_drawing()
    rl.begin_mode_2d(camera)
    rl.clear_background(rl.BLACK)

    rl.draw_rectangle_lines(0, 0, ZOOM_TILE_SIZE * width_ptr[0], ZOOM_TILE_SIZE * height_ptr[0],
                            rl.fade(rl.GRAY, 0.3))

    for layer_i in range(len(map.layers)):
        for x in range(0, width_ptr[0]):
            for y in range(0, height_ptr[0]):
                world_rec = rl.Rectangle(x * ZOOM_TILE_SIZE, y * ZOOM_TILE_SIZE, ZOOM_TILE_SIZE, ZOOM_TILE_SIZE)
                tile_idx = map.layers[layer_i][x,y]
                if tile_idx != 0:
                    tileset.draw_tile(tile_idx, world_rec)

    for e in map.enemies:
        world_rec = rl.Rectangle(e.pos.x * ZOOM_TILE_SIZE, e.pos.y * ZOOM_TILE_SIZE, ZOOM_TILE_SIZE, ZOOM_TILE_SIZE)
        rl.draw_texture_pro(enemy_tex,
                            rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
                            world_rec,
                            (0, 0),
                            0,
                            rl.WHITE)

    rl.draw_texture_pro(zink_tex,
                        rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
                        rl.Rectangle(map.spawn[0] * ZOOM_TILE_SIZE, map.spawn[1] * ZOOM_TILE_SIZE, ZOOM_TILE_SIZE, ZOOM_TILE_SIZE),
                        (0, 0),
                        0,
                        rl.WHITE)

    mouse_pos_world = rl.get_screen_to_world_2d(rl.get_mouse_position(), camera)
    x = int(mouse_pos_world.x // ZOOM_TILE_SIZE)
    y = int(mouse_pos_world.y // ZOOM_TILE_SIZE)
    world_rec = rl.Rectangle(x * ZOOM_TILE_SIZE,
                             y * ZOOM_TILE_SIZE,
                             ZOOM_TILE_SIZE,
                             ZOOM_TILE_SIZE)

    rl.draw_rectangle_lines(int(world_rec.x), int(world_rec.y), int(world_rec.width), int(world_rec.height),
                            rl.WHITE)

    match editor_state:
        case TileEditState(selected_tile=selected_tile):
            if rl.is_key_released(rl.KEY_F):
                flood_fill(map.bg, (x, y), selected_tile)
            else:
                if rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
                    map.bg[x,y] = selected_tile
        case EnemyEditState():
            rl.draw_texture_pro(enemy_tex,
                                rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
                                world_rec,
                                (0, 0),
                                0,
                                rl.fade(rl.WHITE, 0.4))
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                map.enemies.append(Enemy(glm.ivec2(x, y), []))
        case SpawnEditState():
            rl.draw_texture_pro(zink_tex,
                                rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
                                world_rec,
                                (0, 0),
                                0,
                                rl.fade(rl.WHITE, 0.4))
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                map.spawn = glm.vec2(x, y)

    rl.end_mode_2d()
    match editor_state:
        case TileEditState(selected_tile=selected_tile):
            tile_type = COLLISION_TYPES.index(tileset.tiles[selected_tile]['collision'])
            new_tile_type = rl.gui_toggle_group(rl.Rectangle(30, HEIGHT - ZOOM_TILE_SIZE - 35, 100, 30), ';'.join(COLLISION_TYPES), tile_type)
            if tile_type != new_tile_type:
                tileset.set(selected_tile, 'collision', COLLISION_TYPES[new_tile_type])

            for i in range(len(tileset.tiles)):
                display_rect = (i * ZOOM_TILE_SIZE, HEIGHT - ZOOM_TILE_SIZE, ZOOM_TILE_SIZE, ZOOM_TILE_SIZE)
                tileset.draw_tile(i, rl.Rectangle(*display_rect))

                if i == selected_tile:
                    rl.draw_rectangle_lines(*display_rect, rl.WHITE)

    left_col = YLayout()
    with left_col.row(30) as ypos:
        if rl.gui_value_box(rl.Rectangle(60, ypos, 100, 30), "width", width_ptr, 1, MAX_TILES, width_edit_mode):
            width_edit_mode = not width_edit_mode
        width_ptr[0] = min(width_ptr[0], MAX_TILES)
    with left_col.row(30) as ypos:
        if rl.gui_value_box(rl.Rectangle(60, ypos, 100, 30), "height", height_ptr, 1, MAX_TILES, height_edit_mode):
            height_edit_mode = not height_edit_mode
        height_ptr[0] = min(height_ptr[0], MAX_TILES)
    with left_col.row(30) as ypos:
        rl.gui_set_style(rl.LABEL, rl.TEXT_ALIGNMENT, rl.TEXT_ALIGN_RIGHT)
        rl.gui_label(rl.Rectangle(5, ypos, 55, 30), "layer")
        selected_layer = rl.gui_toggle_group(rl.Rectangle(60, ypos, 100, 30), ';'.join(str(x) for x in range(len(map.layers))), selected_layer)

    rl.draw_fps(WIDTH - 100, 10)

    edit_history.update(map)

    rl.end_drawing()

    if rl.get_time() - last_autosave > 30:
        last_autosave = rl.get_time()
        print('autosave')
        edit_history.save_current(mapfile.parent / (mapfile.name + '.autosave'))

# save before close
edit_history.save_current(mapfile)
