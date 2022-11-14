from time import sleep
from typing import List, Optional, Tuple

from checklist import Checklist
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
        return abs(x0 - x1) + abs(y0 - y1) > 90

    def step1(self, state):

        x0, z0 = self.get_location(self.start_state)
        x1, z1 = self.get_location(state)
        return abs(x0 - x1) + abs(z0 - z1) > 1.2


class OpenObjectsTutorial(StepBasedTutorial):
    landing_instruction = "Next, try opening / closing objects"
    instructions = [
        "Turn right and face the cabinet",
        "Press [E] when the cursor is on the cabinet to open it",
        "Press [E] again to close the cabinet",
        "Turn around and walk to the fridge",
        "Press [E] when the cursor is on the fridge to open it",
        "Press [E] again to close the fridge",
    ]
    checklist = [
        "locate cabinet",
        "open cabinet",
        "close cabinet",
        "walk to fridge",
        "open fridge",
        "close fridge",
    ]
    init_steps = get_init_steps("FloorPlan5_tutorial_navigation")

    def get_location(self, state) -> Tuple[float, float]:

        agent_position = state.metadata["agent"]["position"]
        return (agent_position["x"], agent_position["z"])

    def get_look(self, state) -> Tuple[float, float]:

        agent = state.metadata["agent"]
        return (agent["cameraHorizon"], agent["rotation"]["y"])

    def step0(self, state):

        ch, cy = self.get_look(state)
        return -30 <= ch and ch <= -3 and 250 <= cy and ch <= 320

    def step1(self, state):
        return Checklist.is_open(state, "Cabinet")

    def step2(self, state):
        return Checklist.is_close(state, "Cabinet")

    def step3(self, state):

        ch, cy = self.get_look(state)
        x, y = self.get_location(state)
        return (
            5 <= ch
            and ch <= 30
            and 75 <= cy
            and cy <= 105
            and 0.5 <= x
            and x <= 1.4
            and -0.8 <= y
            and y <= -0.2
        )

    def step4(self, state):
        return Checklist.is_open(state, "Fridge")

    def step5(self, state):
        return Checklist.is_close(state, "Fridge")


class PickObjectsTutorial(StepBasedTutorial):

    landing_instruction = "Then, try picking up and putting down objects"
    instructions = [
        "Locate the bread and click on it to pick it up",
        "Click on the counter to put it down",
        "Locate the Knife and click on it to pick it up",
        "Click on the bread to slice it",
        "Click on the counter to put down the knife",
        "Click on a slice of bread to pick it up",
        "Click on the plate to put the slice on the plate",
        "Click on the plate to pick it up with the bread slice",
    ]
    checklist = [
        "pick up bread",
        "put down bread",
        "pick up Knife",
        "slice the bread",
        "put down Knife",
        "pick up bread slice",
        "put bread on plate",
        "pick up plate",
    ]
    init_steps = get_init_steps("FloorPlan5_tutorial_objects")

    def step0(self, state):
        return Checklist.is_picked_up(state, "Bread")

    def step1(self, state):
        return Checklist.is_put_down(state, "Bread")

    def step2(self, state):
        return Checklist.is_picked_up(state, "Knife")

    def step3(self, state):
        return Checklist.exists(state, "BreadSliced")

    def step4(self, state):
        return Checklist.is_put_down(state, "Knife")

    def step5(self, state):
        return Checklist.is_picked_up(state, "BreadSliced")

    def step6(self, state):
        return Checklist.is_put_on(state, "BreadSliced", "Plate")

    def step7(self, state):
        return Checklist.is_picked_up(state, "Plate")


class CoffeeTutorial(StepBasedTutorial):

    landing_instruction = "Last, try making some coffee"
    instructions = [
        "Locate and click on the mug to pick it up",
        "Click on the coffee machine to place to mug",
        "Put the cursor on the coffee machine and press [F] to brew",
        "Wait for the coffee to brew",
        "Click on the mug to pick it up",
        "Walk toward stool and place coffee on the counter nearby",
    ]
    checklist = [
        "pick up mug",
        "place mug in machine",
        "start coffee machine",
        "wait for coffee",
        "pick up coffee mug",
        "put coffee near stool",
    ]
    init_steps = get_init_steps("FloorPlan5_tutorial_coffee")

    def step0(self, state):
        return Checklist.is_picked_up(state, "Mug")

    def step1(self, state):
        return Checklist.is_put_on(state, "Mug", "CoffeeMachine")

    def step2(self, state):
        return any(
            x["isToggled"]
            for x in state.metadata["objects"]
            if x["objectType"] == "CoffeeMachine"
        )

    def step3(self, state):
        return all(
            not x["isToggled"]
            for x in state.metadata["objects"]
            if x["objectType"] == "CoffeeMachine"
        )

    def step4(self, state):
        return Checklist.is_picked_up(state, "Mug")

    def step5(self, state):

        mug_position = [
            x["position"] for x in state.metadata["objects"] if x["objectType"] == "Mug"
        ][0]
        near_stool = mug_position["z"] > 0.5
        return Checklist.is_put_down(state, "Mug") and near_stool


tutorials = [
    NavigationTutorial().as_task(),
    OpenObjectsTutorial().as_task(),
    PickObjectsTutorial().as_task(),
    CoffeeTutorial().as_task(),
]
