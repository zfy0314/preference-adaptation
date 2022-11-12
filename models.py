import json

action_based = json.load(open("strategies.json"))


class ModelBase:
    def __call__(self, state: dict) -> str:
        raise NotImplementedError


class ActionModel(ModelBase):
    def __init__(self, floor_plan: str, actions: list):
        pass


class GreedyModel(ModelBase):
    def __init__(self, floor_plan: str):
        pass


class MinDistanceModel(ModelBase):
    def __init__(self, floor_plan: str):
        pass


def get_model(floor_plan: str, strategy: str):

    if strategy == "greedy":
        return GreedyModel(floor_plan)
    elif strategy == "min_distance":
        return MinDistanceModel(floor_plan)
    else:
        return ActionModel(floor_plan, action_based[strategy])
