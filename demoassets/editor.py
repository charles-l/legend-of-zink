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
import sys

# HACK because relative imports don't work :|
sys.path.append("..")
from util import *
from typing import Literal, Union, Tuple

from tkinter import Tk
from tkinter.filedialog import askopenfilename, asksaveasfilename

Tk().withdraw()  # keep the root Tk window from appearing

WIDTH = 1600
HEIGHT = 1200

MAX_TILES = 40
# larger tiles for display on hidpi machines
ZOOM_TILE_SIZE = TILE_SIZE * 4
COLLISION_TYPES = "none collide".split()


def prompt_for_new_map():
    filename = pathlib.Path(asksaveasfilename())
    return Map(None), pathlib.Path(filename)


def prompt_for_map():
    filename = pathlib.Path(askopenfilename())
    try:
        return Map(filename), filename
    except Exception as e:
        print(e)
        print("failed to load map")
        return Map(None), pathlib.Path("tmp.json")


class Tileset:
    @staticmethod
    def load_tiles(path):
        tiles = {}
        with open(path, "r") as f:
            tiles = json.load(f)
        tex = rl.load_texture(path.replace(".def.json", ".png"))
        for tile in tiles:
            if any(x not in tile for x in ["rect", "collision"]):
                raise Exception("Data doesn't match schema", tile)
            tile["rect"] = rl.Rectangle(*tile["rect"])
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
            r = t["rect"]
            t["rect"] = [r.x, r.y, r.width, r.height]
            output.append(t)

        with open(self.path, "w") as f:
            json.dump(output, f)

    def draw_tile(self, i, target_rect):
        rl.draw_texture_pro(
            self.tex, self.tiles[i]["rect"], target_rect, (0, 0), 0, rl.WHITE
        )


class EditHistory:
    def __init__(self):
        self.undo_stack = collections.deque(maxlen=10)
        self.undo_pos = -1
        self.level_hash = 0
        self.last_save_hash = 0
        self.serialized_map = {}

    def save_current(self, output_file):
        if self.last_save_hash != self.level_hash:
            print("saving")
            with open(output_file, "w") as f:
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
                self.undo_stack.extend(
                    reversed(list(self.undo_stack)[self.undo_pos : -1])
                )
            self.undo_stack.append(pickled_map)
            self.undo_pos = -1
            self.level_hash = new_hash

    def step_history(self, dir: Literal[1, -1], map):
        self.undo_pos += dir
        self.undo_pos = glm.clamp(self.undo_pos, -len(self.undo_stack), -1)
        data = pickle.loads(self.undo_stack[self.undo_pos])
        map.layers, map.enemies, map.trigger_tags, map.spawn = load_map_data(data)
        self.level_hash = hash(self.undo_stack[self.undo_pos])
        return data


def crop(tiles, width, height):
    return [row[:width] for row in tiles[:height]]


class Map:
    def __init__(self, mappath):
        if mappath is None:
            self.enemies = []
            self.layers = [
                Grid([[0] * MAX_TILES for _ in range(MAX_TILES)]) for _ in range(2)
            ]
            self.spawn = glm.vec2(-1, -1)
            self.trigger_tags = {}
        else:
            self.layers, self.enemies, self.trigger_tags, self.spawn = load_map(mappath)
            width_ptr[0] = len(self.layers[0].tiles[0])
            height_ptr[0] = len(self.layers[0].tiles)
            # Resize each layer to be MAX_TILES by MAX_TILES so we can always
            # assume we have that many tiles available.
            for i in range(len(self.layers)):
                self.layers[i].tiles = [
                    row + [0] * (MAX_TILES - len(row)) for row in self.layers[i]
                ] + [[0] * MAX_TILES for _ in range(MAX_TILES - len(self.layers[i]))]

    def serialize(self):
        return {
            "layers": [crop(l.tiles, width_ptr[0], height_ptr[0]) for l in self.layers],
            "enemy_pos": [e.pos.to_tuple() for e in self.enemies],
            "spawn": self.spawn.to_tuple(),
            "trigger_tags": {f"{k[0]} {k[1]}": v for k, v in self.trigger_tags.items()},
        }

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
                queue.append((x + dx, y + dy))


###

rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
rl.init_window(WIDTH, HEIGHT, "Legend of Zink [EDITOR]")
rl.init_audio_device()
rl.set_target_fps(60)

tileset = Tileset("tileset.def.json")
enemy_tex = rl.load_texture("enemy.png")
zink_tex = rl.load_texture("zink.png")

camera = rl.Camera2D()
camera.zoom = 1
camera.offset = WIDTH / 2, HEIGHT / 2

edit_mode = {
    "width": False,
    "height": False,
    "trigger_tag": False,
}

width_ptr = rl.ffi.new("int *")
width_ptr[0] = 40

height_ptr = rl.ffi.new("int *")
height_ptr[0] = 40

trigger_tag_text = rl.ffi.new("char[20]")


@dataclass
class TileEditState:
    tile_def: int = 1


@dataclass
class TriggerEditState:
    selected_tile: Tuple[int, int]


@dataclass
class EnemyEditState:
    selected_enemy: int = 0


@dataclass
class SpawnEditState:
    pass


editor_state: Union[
    TileEditState, TriggerEditState, EnemyEditState, SpawnEditState
] = TileEditState()
selected_layer = 0

# default to map.json
mapfile = pathlib.Path("map.json")
if mapfile.exists():
    map = Map(mapfile)
else:
    map, mapfile = prompt_for_new_map()

edit_history = EditHistory()
edit_history.update(map)
last_autosave = 0


def hot_key_released(key):
    # don't respond to hotkeys when editing text boxes
    if any(edit_mode.values()):
        return False

    mod = None
    if key.startswith("ctrl-"):
        mod = "ctrl"
        key = key.removeprefix("ctrl-")
    is_released = rl.is_key_released(getattr(rl, f"KEY_{key.upper()}"))
    if mod == "ctrl":
        return rl.is_key_down(rl.KEY_LEFT_CONTROL) and is_released
    else:
        return is_released


number_keys = "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE".split()
while not rl.window_should_close():
    mouse_pos_world = rl.get_screen_to_world_2d(rl.get_mouse_position(), camera)

    hoverx, hovery = int(mouse_pos_world.x // ZOOM_TILE_SIZE), int(
        mouse_pos_world.y // ZOOM_TILE_SIZE
    )
    world_rec = rl.Rectangle(
        hoverx * ZOOM_TILE_SIZE, hovery * ZOOM_TILE_SIZE, ZOOM_TILE_SIZE, ZOOM_TILE_SIZE
    )

    if hot_key_released("ctrl-z"):
        edit_history.step_history(-1, map)
    if hot_key_released("ctrl-y"):
        edit_history.step_history(1, map)

    for i, s in enumerate(number_keys):
        if hot_key_released(s) and 0 <= i < len(tileset.tiles):
            editor_state = TileEditState(i)
    if hot_key_released("e"):
        editor_state = EnemyEditState()
    if hot_key_released("s"):
        editor_state = SpawnEditState()
    if hot_key_released("t"):
        editor_state = TriggerEditState((hoverx, hovery))

    if rl.is_mouse_button_down(rl.MOUSE_BUTTON_RIGHT):
        camera.target.x -= rl.get_mouse_delta().x
        camera.target.y -= rl.get_mouse_delta().y

    camera.zoom += rl.get_mouse_wheel_move()
    camera.zoom = glm.clamp(camera.zoom, 0.5, 10)

    rl.begin_drawing()
    rl.begin_mode_2d(camera)
    rl.clear_background(rl.BLACK)

    rl.draw_rectangle_lines(
        0,
        0,
        ZOOM_TILE_SIZE * width_ptr[0],
        ZOOM_TILE_SIZE * height_ptr[0],
        rl.fade(rl.GRAY, 0.3),
    )

    for layer_i in range(len(map.layers)):
        for x in range(0, width_ptr[0]):
            for y in range(0, height_ptr[0]):
                tile_rec = rl.Rectangle(
                    x * ZOOM_TILE_SIZE,
                    y * ZOOM_TILE_SIZE,
                    ZOOM_TILE_SIZE,
                    ZOOM_TILE_SIZE,
                )
                tile_idx = map.layers[layer_i][x, y]
                if tile_idx != 0:
                    tileset.draw_tile(tile_idx, tile_rec)

    for e in map.enemies:
        enemy_world_rec = rl.Rectangle(
            e.pos.x * ZOOM_TILE_SIZE,
            e.pos.y * ZOOM_TILE_SIZE,
            ZOOM_TILE_SIZE,
            ZOOM_TILE_SIZE,
        )
        rl.draw_texture_pro(
            enemy_tex,
            rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
            enemy_world_rec,
            (0, 0),
            0,
            rl.WHITE,
        )

    rl.draw_texture_pro(
        zink_tex,
        rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
        rl.Rectangle(
            map.spawn[0] * ZOOM_TILE_SIZE,
            map.spawn[1] * ZOOM_TILE_SIZE,
            ZOOM_TILE_SIZE,
            ZOOM_TILE_SIZE,
        ),
        (0, 0),
        0,
        rl.WHITE,
    )

    rl.draw_rectangle_lines(
        int(world_rec.x),
        int(world_rec.y),
        int(world_rec.width),
        int(world_rec.height),
        rl.WHITE,
    )

    match editor_state:
        case TileEditState(tile_def=tile_def):
            if hot_key_released("f"):
                flood_fill(map.bg, (hoverx, hovery), tile_def)
            else:
                if rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
                    map.bg[hoverx, hovery] = tile_def
        case TriggerEditState(selected_tile=selected):
            if rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
                editor_state = TriggerEditState((hoverx, hovery))

                edit_mode["trigger_tag"] = True
                # clear out previous tag
                rl.ffi.memmove(
                    trigger_tag_text,
                    b"\x00" * len(trigger_tag_text),
                    len(trigger_tag_text),
                )
                tag = map.trigger_tags.get((hoverx, hovery), "")
                rl.ffi.memmove(
                    trigger_tag_text, tag.encode("ascii"), len(trigger_tag_text)
                )
            for tx, ty in map.trigger_tags:
                rl.draw_rectangle_lines(
                    tx * ZOOM_TILE_SIZE,
                    ty * ZOOM_TILE_SIZE,
                    ZOOM_TILE_SIZE,
                    ZOOM_TILE_SIZE,
                    rl.GREEN,
                )
            rl.draw_rectangle_lines(
                selected[0] * ZOOM_TILE_SIZE + 4,
                selected[1] * ZOOM_TILE_SIZE + 4,
                ZOOM_TILE_SIZE - 8,
                ZOOM_TILE_SIZE - 8,
                rl.WHITE,
            )
        case EnemyEditState():
            rl.draw_texture_pro(
                enemy_tex,
                rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
                world_rec,
                (0, 0),
                0,
                rl.fade(rl.WHITE, 0.4),
            )
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                map.enemies.append(Enemy(glm.ivec2(hoverx, hovery), []))

        case SpawnEditState():
            rl.draw_texture_pro(
                zink_tex,
                rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
                world_rec,
                (0, 0),
                0,
                rl.fade(rl.WHITE, 0.4),
            )
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                map.spawn = glm.vec2(hoverx, hovery)

    rl.end_mode_2d()

    match editor_state:
        case TriggerEditState(selected_tile=selected_tile):
            if edit_mode["trigger_tag"]:
                popup_width = 140
                popup_height = 80
                rect = rl.Rectangle(
                    rl.get_render_width() / 2 - popup_width / 2,
                    rl.get_render_height() / 2 - popup_height / 2,
                    popup_width,
                    popup_height,
                )

                edit_mode["trigger_tag"] = not rl.gui_window_box(rect, "Set Tag")

                if rl.gui_text_box(
                    rl.Rectangle(rect.x + 5, rect.y + 40, rect.width - 10, 30),
                    rl.ffi.cast("char*", trigger_tag_text),
                    len(trigger_tag_text),
                    True,
                ):
                    edit_mode["trigger_tag"] = False
                    tag = rl.ffi.string(trigger_tag_text).decode("ascii")
                    map.trigger_tags[selected_tile] = tag
                    if tag == "" and selected_tile in map.trigger_tags:
                        del map.trigger_tags[selected_tile]
        case TileEditState(tile_def=tile_def):
            tile_type = COLLISION_TYPES.index(tileset.tiles[tile_def]["collision"])
            new_tile_type = rl.gui_toggle_group(
                rl.Rectangle(30, rl.get_render_height() - ZOOM_TILE_SIZE - 35, 100, 30),
                ";".join(COLLISION_TYPES),
                tile_type,
            )
            if tile_type != new_tile_type:
                tileset.set(tile_def, "collision", COLLISION_TYPES[new_tile_type])

            for i in range(len(tileset.tiles)):
                display_rect = (
                    i * ZOOM_TILE_SIZE,
                    rl.get_render_height() - ZOOM_TILE_SIZE,
                    ZOOM_TILE_SIZE,
                    ZOOM_TILE_SIZE,
                )
                tileset.draw_tile(i, rl.Rectangle(*display_rect))

                if i == tile_def:
                    rl.draw_rectangle_lines(*display_rect, rl.WHITE)

    left_col = YLayout()
    with left_col.row(30) as ypos:
        if rl.gui_value_box(
            rl.Rectangle(60, ypos, 100, 30),
            "width",
            width_ptr,
            1,
            MAX_TILES,
            edit_mode["width"],
        ):
            edit_mode["width"] = not edit_mode["width"]
        width_ptr[0] = min(width_ptr[0], MAX_TILES)
    with left_col.row(30) as ypos:
        if rl.gui_value_box(
            rl.Rectangle(60, ypos, 100, 30),
            "height",
            height_ptr,
            1,
            MAX_TILES,
            edit_mode["height"],
        ):
            edit_mode["height"] = not edit_mode["height"]
        height_ptr[0] = min(height_ptr[0], MAX_TILES)
    with left_col.row(30) as ypos:
        rl.gui_set_style(rl.LABEL, rl.TEXT_ALIGNMENT, rl.TEXT_ALIGN_RIGHT)
        rl.gui_label(rl.Rectangle(5, ypos, 55, 30), "layer")
        selected_layer = rl.gui_toggle_group(
            rl.Rectangle(60, ypos, 100, 30),
            ";".join(str(x) for x in range(len(map.layers))),
            selected_layer,
        )
    with left_col.row(30) as ypos:
        if rl.gui_button(rl.Rectangle(60, ypos, 100, 30), "map file"):
            map, mapfile = prompt_for_map()
        if rl.gui_button(rl.Rectangle(170, ypos, 100, 30), "new map"):
            map, mapfile = prompt_for_new_map()

    rl.draw_fps(rl.get_render_width() - 100, 10)

    edit_history.update(map)

    rl.end_drawing()

    if rl.get_time() - last_autosave > 30:
        last_autosave = rl.get_time()
        print("autosave")
        edit_history.save_current(mapfile.parent / (mapfile.name + ".autosave"))

# save before close
edit_history.save_current(mapfile)
