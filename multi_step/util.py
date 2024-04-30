from typing import Text

from rasa.shared.core.trackers import DialogueStateTracker
from rasa.dialogue_understanding.stack.utils import top_flow_frame
import requests


def check_if_tracker_has_active_flow(tracker: DialogueStateTracker) -> bool:
    top_relevant_frame = top_flow_frame(tracker.stack)
    return bool(top_relevant_frame and top_relevant_frame.flow_id)


def invoke_together_ai(prompt: Text) -> Text:
    endpoint = 'https://api.together.xyz/v1/chat/completions'
    res = requests.post(endpoint, json={
        # "model": "mistralai/Mixtral-8x22B-Instruct-v0.1",
        "model": "meta-llama/Llama-3-70b-chat-hf",
        # "model": "lmsys/vicuna-13b-v1.5",
        "max_tokens": 512,
        "temperature": 0.0,
        "top_p": 0.7,
        "top_k": 50,
        "repetition_penalty": 1,
        "stop": [
            "<|eot_id|>"
            # "</s>",
            # "[/INST]"
        ],
        "messages": [
            {
                "content": prompt,
                "role": "system"
            }
        ]
    }, headers={
        "Authorization": "Bearer d5401b7c244083f4a6587e07217a7ca584d0f4a8b41a913ad633b5ccab363e51",
    })
    output = res.json()["choices"][0]["message"]["content"]
    output = output.replace("\_", "_")
    return output
