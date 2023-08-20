from dataclasses import dataclass
import pyray as rl
import glm
import random
import lzma
import json
import pathlib
import pickle
import contextlib
from util import *
from typing import Literal

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
class Map:
    class Layer:
        def __init__(self, map):
            self.tiles = [([0] * MAX_TILES) for _ in range(MAX_TILES)]
            self.map = map

        def __setitem__(self, pos, value):
            if self.tiles[pos[1]][pos[0]] == value:
                return
            self.tiles[pos[1]][pos[0]] = value
            self.map.save()

        def __getitem__(self, pos):
            return self.tiles[pos[1]][pos[0]]

        def __contains__(self, pos):
            return (0 <= pos[0] < len(self.tiles[0]) and
                    0 <= pos[1] < len(self.tiles))

        def __getstate__(self):
            state = self.__dict__.copy()
            del state['map']
            return state


    def __init__(self, nlayers=2):
        self.enable_save = True
        p = pathlib.Path('map.pkl.xz')
        if p.exists():
            with lzma.open(p, 'rb') as f:
                self.layers = pickle.load(f)
                for l in self.layers:
                    l.map = self
        else:
            self.layers = [Map.Layer(self) for _ in range(nlayers)]

    @contextlib.contextmanager
    def transaction(self):
        self.enable_save = False
        yield
        self.enable_save = True
        self.save()

    def save(self):
        if self.enable_save:
            print('saving')
            with lzma.open('map.pkl.xz', 'wb') as lzf:
                pickle.dump(self.layers, lzf)

# track y offset to simplify creating rows in the GUI
@dataclass
class YLayout:
    yoff: float = 5
    padding: float = 5

    @contextlib.contextmanager
    def row(self, height):
        yield self.yoff
        self.yoff += height + self.padding

def flood_fill(tiles, pos, old_tile, new_tile):
    if old_tile == new_tile:
        return
    x, y = pos
    tiles[x, y] = new_tile
    for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
        if (x + dx, y + dy) in tiles and tiles[x + dx, y + dy] == old_tile:
            flood_fill(tiles, (x+dx, y+dy), old_tile, new_tile)

###

rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
rl.init_window(WIDTH, HEIGHT, "Legend of Zink [EDITOR]")
rl.init_audio_device()
rl.set_target_fps(60)

tileset = Tileset("tileset.def.json")

camera = rl.Camera2D()
camera.zoom = 1
camera.offset = WIDTH / 2, HEIGHT / 2

width_edit_mode = False
width_ptr = rl.ffi.new("int *")
width_ptr[0] = 40

height_edit_mode = False
height_ptr = rl.ffi.new("int *")
height_ptr[0] = 40

selected_tile = 1
selected_layer = 0

MAX_TILES = 100
# larger tiles for display on hidpi machines
ZOOM_TILE_SIZE = TILE_SIZE * 4
COLLISION_TYPES = "none trigger collide".split()

map = Map()

number_keys = 'ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE'.split()
while not rl.window_should_close():
    for i, s in enumerate(number_keys):
        if rl.is_key_released(getattr(rl, f'KEY_{s}')) and 0 <= i < len(tileset.tiles):
            selected_tile = i

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

    mouse_pos_world = rl.get_screen_to_world_2d(rl.get_mouse_position(), camera)
    x = int(mouse_pos_world.x // ZOOM_TILE_SIZE)
    y = int(mouse_pos_world.y // ZOOM_TILE_SIZE)
    world_rec = rl.Rectangle(x * ZOOM_TILE_SIZE,
                             y * ZOOM_TILE_SIZE,
                             ZOOM_TILE_SIZE,
                             ZOOM_TILE_SIZE)
    if rl.check_collision_point_rec(mouse_pos_world, world_rec):
        rl.draw_rectangle_lines(int(world_rec.x), int(world_rec.y), int(world_rec.width), int(world_rec.height),
                                rl.WHITE)
        if rl.is_key_released(rl.KEY_F):
            with map.transaction():
                p = (x, y)
                flood_fill(map.layers[selected_layer], p, map.layers[selected_layer][p], selected_tile)
        else:
            if rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
                map.layers[selected_layer][x,y] = selected_tile

    rl.end_mode_2d()

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
    with left_col.row(30) as ypos:
        if rl.gui_value_box(rl.Rectangle(60, ypos, 100, 30), "height", height_ptr, 1, MAX_TILES, height_edit_mode):
            height_edit_mode = not height_edit_mode
    with left_col.row(30) as ypos:
        rl.gui_set_style(rl.LABEL, rl.TEXT_ALIGNMENT, rl.TEXT_ALIGN_RIGHT)
        rl.gui_label(rl.Rectangle(5, ypos, 55, 30), "layer")
        selected_layer = rl.gui_toggle_group(rl.Rectangle(60, ypos, 100, 30), ';'.join(str(x) for x in range(len(map.layers))), selected_layer)

    rl.draw_fps(WIDTH - 100, 10)

    rl.end_drawing()
