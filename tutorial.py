from time import sleep
from typing import List, Optional, Tuple

from utils import Color, DecoratedString, Task, get_init_steps


class StepBasedTutorial:

    landing_instruction: str
    instructions: List[str]
    checklist: List[str]
    init_steps: List[dict]

    def __init__(self):

        self.initialized = False
        self.current_step = 0
        self.total_steps = len(self.instructions)
        self.completed = False

    def banner_func(self, state) -> str:

        if self.completed:
            sleep(1.5)
            return None

        if self.initialized:
            res = getattr(self, "step{}".format(self.current_step))(state)
            try:
                while res and self.current_step < self.total_steps:
                    self.current_step += 1
                    res = getattr(self, "step{}".format(self.current_step))(state)
            except AttributeError:
                self.completed = True
        else:
            self.initialized = True
            self.start_state = state

        try:
            return self.instructions[self.current_step]
        except IndexError:
            return "Completed!"

    def checklist_func(self, state) -> Optional[List[DecoratedString]]:

        if self.completed:
            sleep(1.5)
            return None

        if self.initialized:
            res = getattr(self, "step{}".format(self.current_step))(state)
            try:
                while res and self.current_step < self.total_steps:
                    self.current_step += 1
                    res = getattr(self, "step{}".format(self.current_step))(state)
            except AttributeError:
                self.completed = True
        else:
            self.initialized = True
            self.start_state = state

        return [
            DecoratedString(item, Color.green if i < self.current_step else Color.red)
            for i, item in enumerate(self.checklist)
        ]

    def as_task(self) -> Task:
        return Task(
            name=str(self.__class__),
            banner_func=self.banner_func,
            checklist_func=self.checklist_func,
            init_steps=self.init_steps,
            floor_plan="FloorPlan5",
            instructions=[self.landing_instruction],
        )


class NavigationTutorial(StepBasedTutorial):
    landing_instruction = "First, try moving around"
    instructions = [
        "Move mouse to look around",
        "Use W/A/S/D to move ahead/back/left/right",
    ]
    checklist = [
        "look around",
        "move around",
    ]
    init_steps = get_init_steps("FloorPlan5_tutorial_navigation")

    def get_location(self, state) -> Tuple[float, float]:

        agent_position = state.metadata["agent"]["position"]
        return (agent_position["x"], agent_position["z"])

    def get_look(self, state) -> Tuple[float, float]:

        agent = state.metadata["agent"]
        return (agent["cameraHorizon"], agent["rotation"]["y"])

    def step0(self, state):

        x0, y0 = self.get_look(self.start_state)
        x1, y1 = self.get_look(state)
        return abs(x0 - x1) + abs(y0 - y1) > 180

    def step1(self, state):

        x0, z0 = self.get_location(self.start_state)
        x1, z1 = self.get_location(state)
        return abs(x0 - x1) + abs(z0 - z1) > 2


tutorials = [NavigationTutorial().as_task()]
