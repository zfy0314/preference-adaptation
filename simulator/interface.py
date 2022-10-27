import os
import sys
from pprint import pprint

import pygame
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering

FLOOR_PLAN = "FloorPlan10"
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 900
SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
DEBUG = True

# pygame step
pygame.init()
scrn = pygame.display.set_mode(SCREEN_SIZE)
font = pygame.font.SysFont(None, 100)
scrn.fill((255, 255, 255))
text = font.render("Loading...", True, (0, 0, 0))
text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
scrn.blit(text, text_rect)
pygame.display.flip()


# ai2thor setup
controller = Controller(
    platform=CloudRendering,
    scene=FLOOR_PLAN,
    width=SCREEN_WIDTH,
    height=SCREEN_HEIGHT,
    rotateStepDegrees=30,
    snapToGrid=False,
)
state = controller.step(action="LookDown", degrees=15)
pprint(state)
key_binding = {
    pygame.K_UP: dict(action="LookUp"),
    pygame.K_LEFT: dict(action="RotateLeft"),
    pygame.K_DOWN: dict(action="LookDown"),
    pygame.K_RIGHT: dict(action="RotateRight"),
    pygame.K_w: dict(action="MoveAhead"),
    pygame.K_a: dict(action="MoveLeft", moveMagnitude=0.15),
    pygame.K_s: dict(action="MoveBack"),
    pygame.K_d: dict(action="MoveRight", moveMagnitude=0.15),
    pygame.K_r: dict(  # reset
        action="reset",
        position=dict(x=0.0, y=0.9, z=-1.25),
        rotation=dict(x=0.0, y=90.0, z=0.0),
        horizon=30,
        standing=True,
    ),
}

# game loop
while True:

    scrn.blit(pygame.surfarray.make_surface(state.frame.transpose(1, 0, 2)), (0, 0))
    pygame.display.flip()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            break

        if event.type == pygame.KEYDOWN:
            try:
                action = key_binding[event.key]
            except KeyError:
                pass
            else:
                state = controller.step(**action)
                pprint(state, sys.stdout if DEBUG else os.devnull)
