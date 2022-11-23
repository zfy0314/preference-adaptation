import json
from datetime import datetime, timedelta
from typing import List, Tuple

import ai2thor.controller
import cv2
import fire
from ai2thor.platform import CloudRendering
from tqdm import tqdm


def parse_time(time_str: str) -> datetime:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")


def make_video(
    actions: List[Tuple[str, dict]],
    file_name: str,
    floor_plan: str,
    frame_rate: int = 100,
    size: Tuple[int, int] = (1440, 810),
):

    writer = cv2.VideoWriter(
        file_name, cv2.VideoWriter_fourcc(*"mp4v"), frame_rate, size
    )
    controller = ai2thor.controller.Controller(
        platform=CloudRendering,
        scene=floor_plan,
        width=size[0],
        height=size[1],
        gridSize=0.05,
        snapToGrid=False,
        fieldOfView=60,
    )
    state = controller.step(action="Teleport")
    frame = state.cv2img
    writer.write(frame)
    current = parse_time(actions[0][0])
    i = 0

    with tqdm(total=len(actions)) as pbar:
        while i < len(actions):
            time, action = actions[i]
            while (parse_time(time) < current) and (i < len(actions) - 1):
                state = controller.step(**action)
                i += 1
                pbar.update(1)
                time, action = actions[i]
            if parse_time(time) - current < timedelta(seconds=1 / frame_rate):
                state = controller.step(**action)
                frame = state.cv2img
                time, action = actions[i]
                i += 1
                pbar.update(1)
            writer.write(frame)
            current += timedelta(seconds=1 / frame_rate)
    writer.release()


def make_video_from_results(
    result_file: str,
    video_file: str,
    key: str,
    frame_rate: int = 25,
    size: Tuple[int, int] = (1440, 810),
):
    if key.startswith("FloorPlan"):
        floor_plan = key.split(" ")[0]
    else:
        floor_plan = "FloorPlan5"

    result = json.load(open(result_file, "r"))

    make_video(result["actions"][key], video_file, floor_plan, frame_rate, size)


if __name__ == "__main__":
    fire.Fire()
