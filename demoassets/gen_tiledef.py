import json
import pyray as rl
import argparse
import os.path
from typing import Literal

parser = argparse.ArgumentParser()
parser.add_argument("image", help="image containing the tileset")
args = parser.parse_args()
json_file = os.path.splitext(args.image)[0] + ".def.json"

included_tiles: dict[tuple[int, int], Literal["collide", "none"]] = {}
tile_size = 16

if os.path.exists(json_file):
    with open(json_file, "r") as f:
        d = json.load(f)
    if d:
        print(f">>> Loading previous definition from {json_file}")
        # Use width from first rectangle as tile_size
        # NOTE: assumes all tiles are the same height/width
        tile_size = d[0]["rect"][2]
        included_tiles = {
            (tile["rect"][0] // tile_size, tile["rect"][1] // tile_size): tile[
                "collision"
            ]
            for tile in d
        }

rl.init_window(800, 600, "Tileset generator")

tex = rl.load_texture(args.image)

tile_size_ptr = rl.ffi.new("int *")
tile_size_ptr[0] = tile_size
tile_size_edit = False

SCALE = 2
ORIGIN = (10, 50)

camera = rl.Camera2D(ORIGIN, (0, 0), 0, SCALE)

rl.set_target_fps(60)

# the subset of tile coordinates, mapped to their collision type
while not rl.window_should_close():
    if rl.is_key_released(rl.KEY_F):
        rl.toggle_fullscreen()

    rl.begin_drawing()
    rl.clear_background(rl.BLACK)
    if rl.gui_value_box(
        rl.Rectangle(60, 10, 100, 30),
        "tile size",
        tile_size_ptr,
        1,
        255,
        tile_size_edit,
    ):
        tile_size_edit = not tile_size_edit
        tile_size = tile_size_ptr[0]

    rl.begin_mode_2d(camera)
    rl.draw_texture(tex, 0, 0, rl.WHITE)

    for x in range(tex.width // tile_size + 1):
        rl.draw_line(x * tile_size, 0, x * tile_size, tex.height, rl.PURPLE)

    for y in range(tex.height // tile_size + 1):
        rl.draw_line(0, y * tile_size, tex.width, y * tile_size, rl.PURPLE)

    for tile in included_tiles:
        color = rl.RED if included_tiles[tile] == "collide" else rl.WHITE
        rl.draw_rectangle_lines(
            tile[0] * tile_size, tile[1] * tile_size, tile_size, tile_size, color
        )

    mouse_pos_world = rl.get_screen_to_world_2d(rl.get_mouse_position(), camera)
    mouse_tile = (
        int(mouse_pos_world.x // tile_size),
        int(mouse_pos_world.y // tile_size),
    )

    if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
        if mouse_tile in included_tiles:
            del included_tiles[mouse_tile]
        else:
            included_tiles[mouse_tile] = "none"

    if rl.is_mouse_button_released(rl.MOUSE_BUTTON_RIGHT):
        if included_tiles.get(mouse_tile, None) == "collide":
            included_tiles[mouse_tile] = "none"
        else:
            included_tiles[mouse_tile] = "collide"

    rl.end_mode_2d()
    rl.end_drawing()

with open(json_file, "w") as f:
    json.dump(
        [
            {
                "rect": [
                    tile[0] * tile_size,
                    tile[1] * tile_size,
                    tile_size,
                    tile_size,
                ],
                "collision": included_tiles[tile],
            }
            for tile in included_tiles
        ],
        f,
    )

print(f">>> Wrote tileset definition output to {json_file}")

rl.close_window()
