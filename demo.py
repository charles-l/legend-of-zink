import pyray as rl
import random

WIDTH, HEIGHT = 800, 600
rl.init_window(WIDTH, HEIGHT, "Flappy Demo")
rl.init_audio_device()

bird_tex = rl.load_texture("bird-sheet.png")
hit_sound = rl.load_sound("hit.wav")
flap_sound = rl.load_sound("flap.wav")
background_layers = [rl.load_texture("background.png"), rl.load_texture("buildings.png")]
rl.set_texture_wrap(background_layers[1], rl.TEXTURE_WRAP_REPEAT)

PLAYER_SIZE = 64
PIPE_WIDTH = 40

class GameOver:
    def update(self):
        if rl.is_key_released(rl.KEY_SPACE):
            global state
            state = Flappy()

    def draw(self):
        rl.clear_background(rl.BLACK)
        rl.draw_text("GAME OVER", 100, 100, 20, rl.WHITE)
        rl.draw_text("<hit space to try again>", 100, 250, 20, rl.WHITE)


class Flappy:
    def __init__(self):
        self.player = rl.Rectangle(100, 100, PLAYER_SIZE, PLAYER_SIZE)
        self.dy = 0
        self.pipes = []
        self.passed_pipes = set()

        for i in range(100):
            gap = random.uniform(250, 400)
            top_pipe_y = random.uniform(40, HEIGHT - 40)
            self.pipes.append(rl.Rectangle(300 + i * 200, top_pipe_y - HEIGHT, PIPE_WIDTH, HEIGHT))
            self.pipes.append(rl.Rectangle(300 + i * 200, top_pipe_y + gap, PIPE_WIDTH, HEIGHT))

    def update(self):
        if rl.is_key_pressed(rl.KEY_SPACE):
            self.dy = -14
            rl.play_sound(flap_sound)

        self.dy = min(self.dy + 1, 10)
        self.player.y += self.dy

        for i, p in enumerate(self.pipes):
            p.x -= 2
            if rl.check_collision_recs(p, self.player):
                global state
                state = GameOver()
                rl.play_sound(hit_sound)

            if p.x + PIPE_WIDTH < self.player.x:
                self.passed_pipes.add(i)

    def draw(self):
        rl.clear_background(rl.BLACK)
        rl.draw_texture_pro(background_layers[0], (0, 0, background_layers[0].width, background_layers[0].height), (0, 0, WIDTH, HEIGHT), (0, 0), 0, rl.WHITE)
        rl.draw_texture_pro(background_layers[1], (rl.get_time() * 4, 0, background_layers[1].width, background_layers[1].height), (0, 0, WIDTH, HEIGHT), (0, 0), 0, rl.WHITE)
        frame = 1 if rl.is_key_down(rl.KEY_SPACE) else 0

        rl.draw_texture_pro(bird_tex, rl.Rectangle(bird_tex.height * frame, 0, bird_tex.height, bird_tex.height), self.player, (0, 0), 0, rl.WHITE)

        for rec in self.pipes:
            rl.draw_rectangle_rec(rec, rl.GREEN)

        rl.draw_text(f"score: {len(self.passed_pipes) // 2}", 10, 40, 20, rl.WHITE)

        rl.draw_fps(10, 10)

state = Flappy()

# run game
rl.set_target_fps(60)
try:
    while not rl.window_should_close():
        state.update()
        rl.begin_drawing()
        state.draw()
        rl.end_drawing()
finally:
    rl.close_audio_device()
