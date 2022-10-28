import os
import queue as _queue
import sys
import time
from multiprocessing import Process, Queue
from pprint import pprint
from typing import Callable, Tuple

import _io
import ai2thor
import pygame
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering


class Interface(Process):
    """Async interface for AI2Thor simulator user study

    model: a callable that takes in the state and output an string hint, potentially
           takes a while to process
    """

    white = (255, 255, 255)
    black = (0, 0, 0)
    key_binding = {
        pygame.K_UP: dict(action="LookUp"),
        pygame.K_LEFT: dict(action="RotateLeft"),
        pygame.K_DOWN: dict(action="LookDown"),
        pygame.K_RIGHT: dict(action="RotateRight"),
        pygame.K_w: dict(action="MoveAhead"),
        pygame.K_a: dict(action="MoveLeft", moveMagnitude=0.15),
        pygame.K_s: dict(action="MoveBack"),
        pygame.K_d: dict(action="MoveRight", moveMagnitude=0.15),
    }
    model: Callable[[ai2thor.server.Event], str]
    daemon: bool
    state: Queue
    hint: Queue
    print_output: _io.TextIOWrapper

    def __init__(
        self,
        floor_plan: str,
        screen_size: Tuple[int, int],
        model: Callable[[ai2thor.server.Event], str],
        debug=False,
    ):

        # spawn new process
        super().__init__()
        self.hint = Queue()
        self.state = Queue(1)
        self.daemon = True

        # pygame interface init
        pygame.init()
        pygame.mouse.set_visible(False)
        width, height = screen_size
        offset = height // 10
        screen = pygame.display.set_mode((width, int(height * 1.1)))
        screen.fill(Interface.white)
        banner = pygame.Rect((0, 0), (width, offset))

        # add loading page
        mktext = pygame.font.SysFont(None, height // 10).render
        text = mktext("Loading...", True, Interface.black)
        text_rect = text.get_rect(center=(width // 2, height // 2))
        screen.blit(text, text_rect)
        pygame.display.flip()

        # ai2thor init
        controller = Controller(
            platform=CloudRendering,
            scene=floor_plan,
            width=width,
            height=height,
            rotateStepDegrees=30,
            snapToGrid=False,
        )
        state = controller.step(action="Teleport")  # get initial state
        self.state.put(state)
        agent = state.metadata["agent"]
        Interface.key_binding[pygame.K_r] = dict(  # add reset button
            action="Teleport",
            position=agent["position"],
            rotation=agent["rotation"],
            standing=agent["isStanding"],
            horizon=agent["cameraHorizon"],
        )
        screen.blit(
            pygame.surfarray.make_surface(state.frame.transpose(1, 0, 2)),
            (0, offset),
        )
        pygame.display.flip()

        # start game loop
        self.model = model
        self.print_output = sys.stdout if debug else open(os.devnull, "w")
        self.start()
        print("starting loop in:", self.pid)

        try:
            while True:
                for event in pygame.event.get():

                    if event.type == pygame.QUIT:
                        raise KeyboardInterrupt

                    # handle key press
                    if event.type == pygame.KEYDOWN:
                        try:
                            action = Interface.key_binding[event.key]
                        except KeyError:
                            if event.key == pygame.K_ESCAPE:
                                raise KeyboardInterrupt
                        else:
                            state = controller.step(**action)
                            screen.blit(
                                pygame.surfarray.make_surface(
                                    state.frame.transpose(1, 0, 2)
                                ),
                                (0, offset),
                            )
                            try:
                                self.state.get_nowait()
                            except _queue.Empty:
                                pass
                            finally:
                                self.state.put(state)
                            pygame.display.flip()
                            pprint(state, self.print_output)

                # handle hint
                try:
                    hint = self.hint.get_nowait()
                except _queue.Empty:
                    pass
                else:
                    screen.fill(Interface.white, banner)
                    text = mktext(hint, True, Interface.black)
                    screen.blit(text, (0, 0))
                    pprint("updating hint to: {}".format(hint), self.print_output)
                    pygame.display.flip()

        except KeyboardInterrupt:
            pygame.display.quit()
            pygame.quit()

        finally:
            try:
                self.state.get_nowait()
            except _queue.Empty:
                pass
            finally:
                self.state.put(None)  # sync with background process

    def run(self):
        """Whenever there is a (new) state, process the hint and put it into queue"""

        state = self.state.get()
        while state is not None:  # sync with foreground process
            pprint("[background] get new state", self.print_output)
            t = time.time()
            hint = self.model(state)
            self.hint.put(hint)
            pprint(
                "[background] give new hint {} after {:.3f}s".format(
                    hint, time.time() - t
                ),
                self.print_output,
            )
            state = self.state.get()


if __name__ == "__main__":

    import random

    def dummy_model(state: ai2thor.server.Event) -> str:

        time.sleep(random.randint(0, 3))
        actions = [
            "MoveAhead",
            "MoveLeft",
            "MoveBack",
            "MoveRight",
            "RotateLeft",
            "RotateRight",
            "LookUp",
            "LookDown",
        ]
        return "Recommended Action: {}".format(random.choice(actions))

    Interface("FloorPlan14", (1600, 900), dummy_model, True)
