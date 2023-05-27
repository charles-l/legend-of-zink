# jousting
from dataclasses import dataclass
import pyray as rl
import glm

@dataclass
class Player:
    rect: rl.Rectangle
    vel: glm.vec2

players = [
    Player(
        rl.Rectangle(1, 1, 30, 80),
        glm.vec2(0, 0)),
    Player(
        rl.Rectangle(100, 1, 30, 80),
        glm.vec2(0, 0)),
    ]
WIDTH, HEIGHT = 800, 600

rl.init_window(WIDTH, HEIGHT, "game")
rl.set_target_fps(60)
while not rl.window_should_close():
    players_input = [
        glm.vec2(
            -int(rl.is_key_down(rl.KEY_LEFT)) + int(rl.is_key_down(rl.KEY_RIGHT)),
            -int(rl.is_key_down(rl.KEY_UP)),
            ),
        glm.vec2(
            -int(rl.is_key_down(rl.KEY_A)) + int(rl.is_key_down(rl.KEY_D)),
            -int(rl.is_key_down(rl.KEY_W)),
            )
        ]

    ### input/logic
    start_pos = [glm.vec2(player.rect.x, player.rect.y) for player in players]
    for i, player in enumerate(players):
        if player.rect.y + player.rect.height < HEIGHT:
            player.vel.y += 1
        else:
            if players_input[i].y < 0:
                player.vel.y = -13

        if players_input[i].x != 0:
            player.vel.x = players_input[i].x * 5
        else:
            player.vel.x = 0

        player.rect.x += player.vel.x
        player.rect.y += player.vel.y

    for iter in range(3):
        for i, player in enumerate(players):
            for j, other_player in enumerate(players):
                if i == j:
                    continue
                if rl.check_collision_recs(player.rect, other_player.rect):
                    r = rl.get_collision_rec(player.rect, other_player.rect)
                    print(r.width, r.height)
                    if r.width < r.height:
                        print('width')
                        player.rect.x -= r.width / 2
                        other_player.rect.x += r.width / 2
                    else:
                        print('height')
                        player.rect.y -= r.height / 2
                        other_player.rect.y += r.height / 2

                player.rect.x = glm.clamp(player.rect.x, 0, WIDTH - player.rect.width)
                player.rect.y = glm.clamp(player.rect.y, 0, HEIGHT - player.rect.height)

    for i, player in enumerate(players):
        player.vel = glm.vec2(player.rect.x, player.rect.y) - start_pos[i]

    ### drawing
    rl.begin_drawing()
    rl.clear_background(rl.GRAY)
    for player in players:
        rl.draw_rectangle(int(player.rect.x), int(player.rect.y), int(player.rect.width), int(player.rect.height), rl.GREEN)
    rl.end_drawing()
