import queue as _queue
from multiprocessing import Queue
from typing import List, Optional

import pygame
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering

from utils import Color, DecoratedString, TaskContentBase


class Interface:
    """Interface class for putting everything together

    Layout:
        +===================================+
        |model suggestions output           |
        +------------------------------+----+  ___ checklist of
        |main environment              |    | /    goal propositions
        |                              |    |/
        |                              |    /
        |                              |   /|
        |                              |  / |
        |                              |    |
        |                              |    |
        |                              |    |
        +==============================+====+

    Each subscreen is handled by an individual process, and communicate with each other
    via pipes

    """

    def __init__(self, width: int, height: int, log_file: str):

        # initialization
        self.log_file = log_file
        pygame.init()
        self.simulator_width = width
        self.simulator_height = height
        self.dot_size = height // 80
        self.x_offset = self.simulator_width // 5
        self.y_offset = self.simulator_height // 10
        self.overall_width = int(width * 1.2)
        self.overall_height = int(height * 1.1)
        self.screen = pygame.display.set_mode((self.overall_width, self.overall_height))
        self.screen_center = (self.overall_width // 2, self.overall_height // 2)
        self.simulator_center = (
            self.simulator_width // 2,
            self.simulator_height // 2 + self.y_offset,
        )
        self.simulator_center_right = (
            self.simulator_width // 2 + self.dot_size,
            self.simulator_height // 2 + self.y_offset,
        )
        self.simulator_top_left = (0, self.y_offset + 5)
        self.banner_bbox = (0, 0, self.overall_width, self.y_offset)  # (x, y, w, h)
        self.banner_top_left = (0, 0)
        self.checklist_bbox = (
            self.simulator_width,
            self.y_offset,
            self.x_offset,
            self.simulator_height,
        )
        self.checklist_top_left = (self.simulator_width, self.y_offset)
        pygame.key.set_repeat(30)

        self.text_size_tiny = height // 25
        self.text_size_small = height // 20
        self.text_size_medium = height // 10
        self.text_size_large = height // 5
        self.mktext_tiny = pygame.font.SysFont(None, self.text_size_tiny).render
        self.mktext_small = pygame.font.SysFont(None, self.text_size_small).render
        self.mktext_medium = pygame.font.SysFont(None, self.text_size_medium).render
        self.mktext_large = pygame.font.SysFont(None, self.text_size_large).render
        self.show_loading("Loading everything")

        (self.pipe_to_banner, self.pipe_from_banner) = (Queue(), Queue())
        (self.pipe_to_checklist, self.pipe_from_checklist) = (Queue(), Queue())

        self.key_binding = {
            pygame.K_w: dict(action="MoveAhead"),
            pygame.K_a: dict(action="MoveLeft"),
            pygame.K_s: dict(action="MoveBack"),
            pygame.K_d: dict(action="MoveRight"),
            pygame.K_q: dict(action="ThrowObject", moveMagnitude=20, forceAction=True),
        }

    def run_all(self, tasks: List[TaskContentBase]):

        for content in tasks:
            self.run_task(content)

    def show_loading(self, text: str):

        self.screen.fill(Color.white)
        text = self.mktext_large(text, True, Color.black)
        text_rect = text.get_rect(center=self.screen_center)
        self.screen.blit(text, text_rect)
        pygame.display.flip()

    def update_banner(self, text: str):

        if text != self.banner_text:
            self.screen.fill(Color.white, self.banner_bbox)
            text = self.mktext_medium(text, True, Color.black)
            self.screen.blit(text, self.banner_top_left)
            self.banner_text = text

    def update_checklist(self, texts: List[DecoratedString]):

        if texts != self.checklist_text:
            self.screen.fill(Color.white, self.checklist_bbox)
            left, top = self.checklist_top_left
            for text in texts:
                text = self.mktext_small(text.text, True, Color.black)
                top += self.text_size_small
                self.screen.blit(text, (left, top))
            self.checklist_text = texts

    def update_simulator(self, object_name: Optional[str]):

        image = self.state.frame.transpose((1, 0, 2))
        self.screen.blit(pygame.surfarray.make_surface(image), self.simulator_top_left)
        pygame.draw.circle(
            self.screen, Color.white, self.simulator_center, self.dot_size
        )
        if object_name is not None:
            text = self.mktext_tiny(object_name.split("|")[0], True, Color.white)
            self.screen.blit(text, self.simulator_center_right)

    def run_task(self, content: TaskContentBase):

        # initialization
        self.show_loading("Loading")
        pygame.mouse.set_visible(False)
        keyclick = pygame.time.Clock()
        self.banner = content.get_banner(self.pipe_to_banner, self.pipe_from_banner)
        self.checklist = content.get_checklist(
            self.pipe_to_checklist, self.pipe_from_checklist
        )
        self.controller = Controller(
            platform=CloudRendering,
            scene=content.ai2thor_floor_plan,
            width=self.simulator_width,
            height=self.simulator_height,
            gridSize=0.05,
            snapToGrid=False,
            fieldOfView=60,
        )
        self.state = self.controller.step(action="Teleport")
        for action in content.ai2thor_init_steps:
            self.state = self.controller.step(**action)
        self.banner_text = ""
        self.checklist_text = []

        # simulator specific
        toggleables = {
            pygame.K_e: {
                obj["objectId"]: ("OpenObject", "CloseObject")
                for obj in self.state.metadata["objects"]
                if obj["openable"]
            },
            pygame.K_f: {
                obj["objectId"]: ("ToggleObjectOn", "ToggleObjectOff")
                for obj in self.state.metadata["objects"]
                if obj["toggleable"]
            },
        }
        has_knife = False

        # load up models
        self.pipe_to_banner.put(self.state)
        self.pipe_to_checklist.put(self.state)
        banner = self.pipe_from_banner.get()
        checklist = self.pipe_from_checklist.get()
        self.update_banner(banner)
        self.update_checklist(checklist)

        # loop
        try:
            while banner is not None and checklist is not None:

                old_state = self.state
                query = self.controller.step(action="GetObjectInFrame", x=0.5, y=0.5)
                objectId = query.metadata["actionReturn"] if query else None

                # handle keyboard & mouse click
                for event in pygame.event.get():

                    if event.type == pygame.KEYDOWN:
                        action = None
                        try:
                            # navigating with W/A/S/D
                            action = self.key_binding[event.key]
                        except KeyError:
                            if keyclick.tick() > 250:
                                # object interaction with E/F
                                try:
                                    action_dict = toggleables[event.key]
                                    (action, alternative) = action_dict[objectId]
                                    action_dict[objectId] = (alternative, action)
                                    action = dict(action=action, objectId=objectId)
                                except KeyError:
                                    # quit
                                    if event.key == pygame.K_ESCAPE:
                                        raise KeyboardInterrupt
                        finally:
                            if action is not None:
                                self.state = self.controller.step(**action)

                    elif event.type == pygame.MOUSEBUTTONDOWN and objectId is not None:
                        for action in [
                            "PutObject",
                            "PickupObject",
                            "SliceObject",
                        ]:
                            if action != "SliceObject" or has_knife:
                                self.state = self.controller.step(
                                    action=action, objectId=objectId
                                )
                                if self.state.metadata["lastActionSuccess"]:
                                    has_knife = (
                                        has_knife and not action == "PutObject"
                                    ) or (
                                        action == "PickupObject" and "Knife" in objectId
                                    )
                                    break

                # handle mouse movement
                x, y = pygame.mouse.get_pos()
                dx, dy = x - self.simulator_center[0], y - self.simulator_center[1]
                pygame.mouse.set_pos(self.simulator_center)
                if dx != 0:
                    self.state = self.controller.step(
                        action="RotateRight", degrees=0.3 * dx
                    )
                if dy > 0:
                    self.state = self.controller.step(
                        action="LookDown", degrees=abs(0.3 * dy)
                    )
                elif dy < 0:
                    self.state = self.controller.step(
                        action="LookUp", degrees=abs(0.3 * dy)
                    )
                pygame.mouse.set_pos(self.simulator_center)

                # update display
                self.pipe_to_banner.put(self.state)
                self.pipe_to_checklist.put(self.state)
                if old_state != self.state:
                    self.update_simulator(objectId)
                try:
                    banner = self.pipe_from_banner.get_nowait()
                except _queue.Empty:
                    pass
                else:
                    self.update_banner(banner)
                try:
                    checklist = self.pipe_from_checklist.get_nowait()
                except _queue.Empty:
                    pass
                else:
                    self.update_checklist(checklist)
                pygame.display.flip()

        except KeyboardInterrupt:
            pass

        # clean up
        self.clean_up(close=False)

    def clean_up(self, close: bool = False):

        self.show_loading("cleaning up")
        try:
            self.pipe_to_banner.put(None)
        except EOFError:
            pass
        try:
            self.pipe_to_checklist.put(None)
        except EOFError:
            pass
        self.banner.join()
        self.checklist.join()
        while not self.pipe_from_banner.empty():
            _ = self.pipe_from_banner.get()
        while not self.pipe_for_checklist.empty():
            _ = self.pipe_for_checklist.get()
        while not self.pipe_to_banner.empty():
            _ = self.pipe_to_banner.get()
        while not self.pipe_to_checklist.empty():
            _ = self.pipe_to_checklist.get()

        if close:
            self.pipe_to_banner.close()
            self.pipe_to_checklist.close()
            pygame.display.quit()
            pygame.quit()


if __name__ == "__main__":

    from dummy import Dummy

    E = Interface(1600, 900, "log")
    E.run_all([Dummy()])
