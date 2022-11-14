from checklist import SandwichChecklist
from utils import floorplans_config


class ModelBase:
    def __init__(self, floor_plan: str):
        self.checklist = SandwichChecklist()
        self.floor_plan_config = floorplans_config.get(floor_plan, {})


class SandwichFirstModel(ModelBase):
    def __call__(self, state: dict) -> str:
        raise NotImplementedError


class CoffeeFirstModel(ModelBase):
    def __call__(self, state: dict) -> str:
        raise NotImplementedError


class GreedyModel(ModelBase):
    def __call__(self, state: dict) -> str:
        raise NotImplementedError


class MinDistanceModel(ModelBase):
    def __call__(self, state: dict) -> str:
        raise NotImplementedError


models = {
    "greedy": GreedyModel,
    "min_distance": MinDistanceModel,
    "empty": lambda floor_plan: lambda state: "",
    "coffee_first": CoffeeFirstModel,
    "sandwich_first": SandwichFirstModel,
}


def get_model(floor_plan: str, strategy: str):
    return models[strategy](floor_plan)
