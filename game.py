import pyray as rl, glm, util

WIDTH, HEIGHT = 800, 600
rl.init_window(WIDTH, HEIGHT, "My awesome game")

state = None

def update(state):
    ...

def draw(state):
    ...

while not rl.window_should_close():
    rl.begin_drawing()
    rl.end_drawing()
