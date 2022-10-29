import os
import pdb
import queue as _queue
import sys
import time
from multiprocessing import Process, Queue
from pprint import pprint
from typing import Callable, List, Tuple

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
        pygame.K_w: dict(action="MoveAhead"),
        pygame.K_a: dict(action="MoveLeft"),
        pygame.K_s: dict(action="MoveBack"),
        pygame.K_d: dict(action="MoveRight"),
    }
    instructions = [
        "Instructions:",
        "Press [ESC] to quit",
        "Press [E] to open/close {fridge, cupboard, microwave ...}",
        "Press [F] to turn on/off {stove, microwave, coffee machine, ...}",
    ]
    daemon: bool = True
    model: Callable[[ai2thor.server.Event], str]
    state: Queue
    hint: Queue
    print_output: _io.TextIOWrapper

    def _show_instructions(
        self,
        instructions: List[str],
        screen: pygame.Surface,
        mktext: callable,
        center: Tuple[int, int],  # top middle
        button_bbox: Tuple[int, int, int, int],  # (left, top, width, height)
        button_text="continue",
    ):
        """Show the instructions until the participant dismiss it"""

        # add instructions
        x, y = center
        for i, instruction in enumerate(instructions):
            text = mktext(instruction, True, Interface.black)
            text_rect = text.get_rect(center=(x, (1.5 + i) * y))
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

    def _update_display_with_circle(
        self,
        screen: pygame.Surface,
        center: Tuple[int, int],
        size: int,
        color: Tuple[int, int, int],
    ):
        """Put a circle at the center of the display then update"""

        pygame.draw.circle(screen, color, center, size)
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
        mktext = pygame.font.SysFont(None, height // 12).render
        self._show_instructions(
            Interface.instructions,
            screen,
            mktext,
            (width // 2, offset),
            (offset, height - offset, 400, offset),
        )
        pygame.mouse.set_visible(False)
        keyclick = pygame.time.Clock()

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
            fieldOfView=60,
        )
        state = controller.step(action="Teleport")  # get initial state
        openables = {
            obj["objectId"]: ("OpenObject", "CloseObject")
            for obj in state.metadata["objects"]
            if obj["openable"]
        }
        toggleables = {
            obj["objectId"]: ("ToggleObjectOn", "ToggleObjectOff")
            for obj in state.metadata["objects"]
            if obj["toggleable"]
        }
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
        # pygame.display.flip()
        self._update_display_with_circle(screen, center, offset // 8, Interface.white)
        pygame.mouse.set_pos(center)

        # start game loop
        self.model = model
        self.print_output = sys.stdout if debug else open(os.devnull, "w")
        self.start()
        print("starting loop in:", self.pid)

        # TODO: code refactor
        try:
            while True:
                old_state = state

                # handle input
                for event in pygame.event.get():

                    if event.type == pygame.QUIT:
                        raise KeyboardInterrupt

                    # handle key press
                    elif event.type == pygame.KEYDOWN:
                        action = None
                        try:
                            action = Interface.key_binding[event.key]
                        except KeyError:
                            if event.key == pygame.K_ESCAPE:
                                raise KeyboardInterrupt
                            elif event.key == pygame.K_p:
                                pdb.set_trace()

                            # handle object interaction with keyboard
                            if event.key == pygame.K_e and keyclick.tick() > 250:
                                query = controller.step(
                                    action="GetObjectInFrame",
                                    x=0.5,
                                    y=0.5,
                                )
                                if query:
                                    objectId = query.metadata["actionReturn"]
                                    try:
                                        (action, alternative) = openables[objectId]
                                        openables[objectId] = (alternative, action)
                                        action = dict(action=action, objectId=objectId)
                                    except KeyError:
                                        pass

                            elif event.key == pygame.K_f and keyclick.tick() > 250:
                                query = controller.step(
                                    action="GetObjectInFrame",
                                    x=0.5,
                                    y=0.5,
                                )
                                if query:
                                    objectId = query.metadata["actionReturn"]
                                    try:
                                        (action, alternative) = toggleables[objectId]
                                        toggleables[objectId] = (alternative, action)
                                        action = dict(action=action, objectId=objectId)
                                    except KeyError:
                                        pass

                            elif event.key == pygame.K_q and keyclick.tick() > 500:
                                action = dict(
                                    action="ThrowObject",
                                    moveMagnitude=20,
                                    forceAction=True,
                                )

                        finally:
                            if action is not None:
                                state = controller.step(**action)
                                pprint(state, stream=self.print_output)

                    # handle object interaction with mouse
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        query = controller.step(
                            action="GetObjectInFrame",
                            x=0.5,
                            y=0.5,
                        )
                        if query:
                            objectId = query.metadata["actionReturn"]
                            for action in [
                                "PutObject",
                                "PickupObject",
                            ]:
                                state = controller.step(
                                    action=action, objectId=objectId
                                )
                                pprint(state, stream=self.print_output)
                                if state.metadata["lastActionSuccess"]:
                                    break

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
                    self._update_display_with_circle(
                        screen, center, offset // 8, Interface.white
                    )
                    pygame.display.flip()
                    pprint(state, stream=self.print_output)

                # update hint
                try:
                    hint = self.hint.get_nowait()
                except _queue.Empty:
                    pass
                else:
                    screen.fill(Interface.white, banner)
                    text = mktext(hint, True, Interface.black)
                    screen.blit(text, (0, 0))
                    pprint(
                        "updating hint to: {}".format(hint), stream=self.print_output
                    )
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
            pprint("[background] get new state", stream=self.print_output)
            t = time.time()
            hint = self.model(state)
            self.hint.put(hint)
            pprint(
                "[background] give new hint {} after {:.3f}s".format(
                    hint, time.time() - t
                ),
                stream=self.print_output,
            )
            state = self.state.get()


if __name__ == "__main__":

    import random

    def dummy_model(state: ai2thor.server.Event) -> str:

        fib = lambda x: x if x < 2 else fib(x - 1) + fib(x - 2)
        _ = fib(random.randint(30, 40))  # mimic computation heavy step
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
