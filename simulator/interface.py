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
    state: a cross-process placeholder for the state (implemented as size 1 queue)
    hint: a cross-process queue for the hints generated
    print_output: redirected output stream
    """

    white = (255, 255, 255)
    gray = (128, 128, 128)
    black = (0, 0, 0)
    key_binding = {
        # pygame.K_UP: dict(action="LookUp"),
        # pygame.K_LEFT: dict(action="RotateLeft"),
        # pygame.K_DOWN: dict(action="LookDown"),
        # pygame.K_RIGHT: dict(action="RotateRight"),
        pygame.K_w: dict(action="MoveAhead"),
        pygame.K_a: dict(action="MoveLeft"),
        pygame.K_s: dict(action="MoveBack"),
        pygame.K_d: dict(action="MoveRight"),
    }
    instruction = "Press [ESC] to quit"
    daemon: bool = True
    model: Callable[[ai2thor.server.Event], str]
    state: Queue
    hint: Queue
    print_output: _io.TextIOWrapper

    def _show_instructions(
        self,
        instruction: str,
        screen: pygame.Surface,
        mktext: callable,
        center: Tuple[int, int],
        button_bbox: Tuple[int, int, int, int],  # (left, top, width, height)
        button_text="continue",
    ):
        """Show the instructions until the participant dismiss it"""

        # add instructions
        text = mktext(instruction, True, Interface.black)
        text_rect = text.get_rect(center=center)
        screen.blit(text, text_rect)

        # wait till the participant click on the button
        left, top, width, height = button_bbox
        text = mktext(button_text, True, Interface.white)
        text_rect = text.get_rect(center=(left + width // 2, top + height // 2))
        inbox = (
            lambda x, y: left <= x
            and x <= left + width
            and top <= y
            and y <= top + height
        )
        try:
            while True:

                # add button
                if inbox(*pygame.mouse.get_pos()):
                    pygame.draw.rect(screen, Interface.black, button_bbox)
                else:
                    pygame.draw.rect(screen, Interface.gray, button_bbox)
                screen.blit(text, text_rect)
                pygame.display.flip()

                for event in pygame.event.get():
                    if (event.type == pygame.QUIT) or (
                        event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                    ):
                        exit()
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if inbox(*pygame.mouse.get_pos()):
                            raise KeyboardInterrupt

        except KeyboardInterrupt:
            pass
        finally:
            pygame.display.flip()

    def __init__(
        self,
        floor_plan: str,
        screen_size: Tuple[int, int],
        model: Callable[[ai2thor.server.Event], str],
        mouse_fraction: float = 0.3,
        debug=False,
    ):
        """
        mouse_fraction: pixel value of the mouse vs degrees rotated
        debug: whether expose info to stdout
        """

        # spawn new process
        super().__init__()
        self.hint = Queue()
        self.state = Queue(1)

        # pygame interface init
        pygame.init()
        pygame.key.set_repeat(30)
        width, height = screen_size
        offset = height // 10
        center = (width // 2, offset + height // 2)
        screen = pygame.display.set_mode((width, int(height * 1.1)))
        screen.fill(Interface.white)
        banner = pygame.Rect((0, 0), (width, offset))
        mktext = pygame.font.SysFont(None, height // 10).render
        self._show_instructions(
            Interface.instruction,
            screen,
            mktext,
            center,
            (offset, height - offset, 400, offset),
        )
        pygame.mouse.set_visible(False)

        # add loading page
        screen.fill(Interface.white)
        text = mktext("Loading...", True, Interface.black)
        text_rect = text.get_rect(center=center)
        screen.blit(text, text_rect)
        pygame.display.flip()

        # ai2thor init
        controller = Controller(
            platform=CloudRendering,
            scene=floor_plan,
            width=width,
            height=height,
            # rotateStepDegrees=30,
            gridSize=0.05,
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
        pygame.mouse.set_pos(center)

        # start game loop
        self.model = model
        self.print_output = sys.stdout if debug else open(os.devnull, "w")
        self.start()
        print("starting loop in:", self.pid)

        try:
            while True:
                old_state = state

                # handle input
                for event in pygame.event.get():

                    if event.type == pygame.QUIT:
                        raise KeyboardInterrupt

                    # handle key press
                    elif event.type == pygame.KEYDOWN:
                        try:
                            action = Interface.key_binding[event.key]
                        except KeyError:
                            if event.key == pygame.K_ESCAPE:
                                raise KeyboardInterrupt
                        else:
                            state = controller.step(**action)

                # handle mouse movement
                x, y = pygame.mouse.get_pos()
                dx, dy = x - center[0], y - center[1]
                pygame.mouse.set_pos(center)
                if dx != 0:
                    state = controller.step(
                        action="RotateRight", degrees=mouse_fraction * dx
                    )
                if dy > 0:
                    state = controller.step(
                        action="LookDown", degrees=abs(mouse_fraction * dy)
                    )
                elif dy < 0:
                    state = controller.step(
                        action="LookUp", degrees=abs(mouse_fraction * dy)
                    )

                # update display
                if state is not old_state:
                    screen.blit(
                        pygame.surfarray.make_surface(state.frame.transpose(1, 0, 2)),
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

                # update hint
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

    Interface("FloorPlan10", (1600, 900), dummy_model, True)
