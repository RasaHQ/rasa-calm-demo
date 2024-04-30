from typing import Text

from rasa.shared.core.trackers import DialogueStateTracker
from rasa.dialogue_understanding.stack.utils import top_flow_frame
import requests


def check_if_tracker_has_active_flow(tracker: DialogueStateTracker) -> bool:
    top_relevant_frame = top_flow_frame(tracker.stack)
    return bool(top_relevant_frame and top_relevant_frame.flow_id)

