import queue as _queue
from multiprocessing import Queue
from typing import List, Optional, Union
from random import shuffle
from time import time

import fire
import ai2thor.controller as controller
import pygame
from ai2thor.platform import CloudRendering

from utils import AsyncFuncWrapper, Color, DecoratedString, Survey, Task, Logger


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

        self.logger = Logger(log_file)
        pygame.init()
        self.simulator_width = width
        self.simulator_height = height
        self.dot_size = height // 80
        self.x_offset = self.simulator_width // 5
        self.y_offset = self.simulator_height // 10
        self.overall_width = int(width * 1.2)
        self.overall_height = int(height * 1.1)
        self.text_size_tiny = height // 25
        self.text_size_small = height // 20
        self.text_size_medium = height // 10
        self.text_size_large = height // 5
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
        self.checklist_top_left = (self.simulator_width + 5, self.y_offset + 5)
        self.confirm_button_bbox = (
            width - self.x_offset,
            height - 2 * self.y_offset,
            self.x_offset,
            self.y_offset,
        )
        self.confirm_button_center = (
            width - self.x_offset // 2,
            height - self.y_offset - self.y_offset // 2,
        )
        self.survey_disagree_loc = (
            self.overall_width // 2 - 1.8 * self.x_offset,
            self.overall_height // 2 - self.text_size_medium,
        )
        self.survey_agree_loc = (
            self.overall_width // 2 + 1.8 * self.x_offset,
            self.overall_height // 2 - self.text_size_medium,
        )
        self.survey_button_locs = [
            (self.overall_width // 2 - 1.8 * self.x_offset, self.overall_height // 2),
            (self.overall_width // 2 - 1.2 * self.x_offset, self.overall_height // 2),
            (self.overall_width // 2 - 0.6 * self.x_offset, self.overall_height // 2),
            (self.overall_width // 2, self.overall_height // 2),
            (self.overall_width // 2 + 0.6 * self.x_offset, self.overall_height // 2),
            (self.overall_width // 2 + 1.2 * self.x_offset, self.overall_height // 2),
            (self.overall_width // 2 + 1.8 * self.x_offset, self.overall_height // 2),
        ]
        pygame.key.set_repeat(30)

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
        }
        self.discrete_key_binding = {
            pygame.K_q: dict(action="ThrowObject", moveMagnitude=20, forceAction=True),
            # pygame.K_r: dict(action="RotateHeldObject", pitch=90, yaw=0, roll=0),
        }

    def run_all(self, tasks: List[Union[Task, Survey, List]]):

        for task in tasks:
            if isinstance(task, Task):
                self.run_task(task)
            elif isinstance(task, Survey):
                self.show_survey(task)
            elif isinstance(task, list):
                self.show_instructions(task)
            else:
                print("skipping: ", task)

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

    def run_task(self, task: Task):

        # initialization
        self.show_loading("Loading")
        keyclick = pygame.time.Clock()
        self.banner = AsyncFuncWrapper(
            task.banner_func, self.pipe_to_banner, self.pipe_from_banner
        )
        self.checklist = AsyncFuncWrapper(
            task.checklist_func, self.pipe_to_checklist, self.pipe_from_checklist
        )
        self.controller = controller.Controller(
            platform=CloudRendering,
            scene=task.floor_plan,
            width=self.simulator_width,
            height=self.simulator_height,
            gridSize=0.05,
            snapToGrid=False,
            fieldOfView=60,
        )
        self.state = self.controller.step(action="Teleport")
        for action in task.init_steps:
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

        # loop
        if task.instructions is not None:
            self.show_instructions(task.instructions)
        pygame.mouse.set_visible(False)
        self.update_banner(banner)
        self.update_checklist(checklist)
        try:
            while banner is not None and checklist is not None:

                old_state = self.state
                query = self.controller.step(action="GetObjectInFrame", x=0.5, y=0.48)
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
                                    action = self.discrete_key_binding.get(
                                        event.key, None
                                    )

                                    # quit
                                    if event.key == pygame.K_ESCAPE:
                                        raise KeyboardInterrupt
                        finally:
                            if action is not None:
                                self.logger.log_action(action)
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
                                    self.logger.log_action(action)
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
                    action = dict(action="RotateRight", degress=0.3 * dx)
                    self.logger.log_action(action)
                    self.state = self.controller.step(action)
                if dy > 0:
                    action = dict(action="LookDown", degrees=abs(0.3 * dy))
                    self.logger.log_action(action)
                    self.state = self.controller.step(action)
                elif dy < 0:
                    action = dict(action="LookUp", degrees=abs(0.3 * dy))
                    self.logger.log_action(action)
                    self.state = self.controller.step(action)
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
                    if banner is None:
                        raise KeyboardInterrupt
                    else:
                        self.update_banner(banner)
                try:
                    checklist = self.pipe_from_checklist.get_nowait()
                except _queue.Empty:
                    pass
                else:
                    if checklist is None:
                        raise KeyboardInterrupt
                    else:
                        self.update_checklist(checklist)
                pygame.display.flip()

        except KeyboardInterrupt:
            pass

        # clean up
        self.logger.save()
        self.clean_up(close=False)

    def show_survey(self, survey: Survey) -> int:

        self.screen.fill(Color.white)
        pygame.mouse.set_visible(True)
        text = self.mktext_medium("    " + survey.question, True, Color.black)
        self.screen.blit(text, self.simulator_top_left)
        button_rects = []
        for i, center in enumerate(self.survey_button_locs):
            text = self.mktext_medium("  {}  ".format(i + 1), True, Color.white)
            button_rects.append(text.get_rect(center=center))
        text = self.mktext_small("strongly agree", True, Color.gray1)
        self.screen.blit(text, text.get_rect(center=self.survey_agree_loc))
        text = self.mktext_small("strongly disagree", True, Color.gray1)
        self.screen.blit(text, text.get_rect(center=self.survey_disagree_loc))

        # wait till the participant click on the button
        text = self.mktext_medium("  confirm  ", True, Color.white)
        text_rect = text.get_rect(center=self.confirm_button_center)
        left, top, width, height = tuple(text_rect)
        self.screen.blit(text, text_rect)
        inbox = (
            lambda mouse, rect: rect[0] <= mouse[0]
            and mouse[0] <= rect[0] + rect[2]
            and rect[1] <= mouse[1]
            and mouse[1] <= rect[1] + rect[3]
        )
        res = -1
        try:
            while True:

                for i, bbox in enumerate(button_rects):
                    if i == res:
                        pygame.draw.rect(self.screen, Color.black, bbox)
                    else:
                        if inbox(pygame.mouse.get_pos(), bbox):
                            pygame.draw.rect(self.screen, Color.gray1, bbox)
                        else:
                            pygame.draw.rect(self.screen, Color.gray2, bbox)

                if inbox(pygame.mouse.get_pos(), text_rect):
                    if res == -1:
                        pygame.draw.rect(self.screen, Color.gray1, text_rect)
                    else:
                        pygame.draw.rect(self.screen, Color.black, text_rect)
                else:
                    pygame.draw.rect(self.screen, Color.gray2, text_rect)
                self.screen.blit(text, text_rect)
                pygame.display.flip()

                for event in pygame.event.get():
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        pos = pygame.mouse.get_pos()
                        if inbox(pos, text_rect) and res != -1:
                            raise KeyboardInterrupt
                        for i, bbox in enumerate(button_rects):
                            if inbox(pos, bbox):
                                res = i

        except KeyboardInterrupt:
            pass
        except:
            self.logger.log_survey(survey.name, res)

    def show_instructions(self, instructions: List[str]):

        # add instructions
        self.screen.fill(Color.white)
        pygame.mouse.set_visible(True)
        left, top = self.simulator_top_left
        left += 5
        top += 5
        for instruction in instructions:
            text = self.mktext_medium("  " + instruction, True, Color.black)
            self.screen.blit(text, (left, top))
            top += self.text_size_medium

        # wait till the participant click on the button
        text = self.mktext_medium(" continue ", True, Color.white)
        text_rect = text.get_rect(center=self.confirm_button_center)
        left, top, width, height = tuple(text_rect)
        self.screen.blit(text, text_rect)
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
                    pygame.draw.rect(self.screen, Color.black, text_rect)
                else:
                    pygame.draw.rect(self.screen, Color.gray1, text_rect)
                self.screen.blit(text, (left, top))
                pygame.display.flip()

                for event in pygame.event.get():
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if inbox(*pygame.mouse.get_pos()):
                            raise KeyboardInterrupt

        except KeyboardInterrupt:
            pass

    def clean_up(self, close: bool = False):

        self.show_loading("cleaning up")
        self.banner.kill()
        self.checklist.kill()
        self.pipe_to_banner.close()
        self.pipe_from_banner.close()
        self.pipe_to_checklist.close()
        self.pipe_from_checklist.close()

        if close:
            pygame.display.quit()
            pygame.quit()
        else:
            self.pipe_to_banner = Queue()
            self.pipe_from_banner = Queue()
            self.pipe_to_checklist = Queue()
            self.pipe_from_checklist = Queue()


def dummy():
    from dummy import dummy_procedures

    E = Interface(1440, 810, "log")
    E.run_all(dummy_procedures)
    E.clean_up(close=True)


def experiment(trial: int):

    all_floor_plans = ["FloorPlan14"] * 5  # TODO: change to actual
    all_strategies = ["Coffee_first"] * 5  # TODO: change to actual
    shuffle(all_floor_plans)
    shuffle(all_strategies)
    tasks = [
        Task(
            name=floor_plan + " " + strategy,
            banner_func=get_strategy(strategy),
            checklist_func=get_checklist(floor_plan),
            floor_plan=floor_plan,
            init_steps=get_init_steps(floor_plan),
            instructions=[
                "You are now in a new kitchen, and you are making the same breakfast.",
                "A new agent will provide optional suggestions on what to do next.",
            ],
        )
        for floor_plan, strategy in zip(all_floor_plans, all_strategies)
    ]

    procedures = [
        *tutorials,
        training,
        *post_train_surveys,
        *sum([[task] + post_train_surveys for task in tasks], []),
    ]
    E = Interface(
        1440, 810, "results/result_participant_{:02d}-{}.pkl".format(trial, time())
    )
    E.run_all(procedures)
    E.clean_up(close=True)


if __name__ == "__main__":
    fire.Fire()
