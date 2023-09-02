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

def crop(tiles, width, height):
    return [row[:width] for row in tiles[:height]]

class Map:
    def __init__(self, mappath):
        if mappath is None:
            self.enemies = []
            self.layers = [Grid([[0] * MAX_TILES for _ in range(MAX_TILES)]) for _ in range(2)]
        else:
            self.layers, self.enemies = load_map(mappath)
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
                'enemy_pos': [e.pos.to_tuple() for e in self.enemies]}

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

editor_state: Union[TileEditState, EnemyEditState] = TileEditState()
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
last_map_hash = hash(pickle.dumps(map.serialize()))
undo_stack = collections.deque(maxlen=10)

number_keys = 'ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE'.split()
while not rl.window_should_close():
    for i, s in enumerate(number_keys):
        if rl.is_key_released(getattr(rl, f'KEY_{s}')) and 0 <= i < len(tileset.tiles):
            editor_state = TileEditState(i)
    if rl.is_key_released(rl.KEY_E):
        editor_state = EnemyEditState()

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
                                rl.WHITE)
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                map.enemies.append(Enemy(glm.ivec2(x, y), []))

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

    # save the map if it changed
    serialized_map = map.serialize()
    new_map_pickle = pickle.dumps(serialized_map)
    new_hash = hash(new_map_pickle)
    if last_map_hash != new_hash:
        last_map_hash = new_hash

        undo_stack.append(new_map_pickle)

        print('saving')
        with open(mapfile, 'w') as f:
            json.dump(serialized_map, f)

    rl.end_drawing()
