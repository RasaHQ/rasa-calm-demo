import logging
from typing import Any, Dict, List, Text
from datetime import datetime

from rasa_sdk import Action

logger = logging.getLogger(__name__)

class ActionShowSlots(Action):
    def name(self):
        return "action_ask_current_card_name"

    def run(self, dispatcher, tracker, domain):
        events = []
        cards = tracker.get_slot("cards")
        if not cards:
            dispatcher.utter_message(text="No cards found.")
        else:
            buttons = []
            for card in cards:
                buttons.append(
                    {
                        "title": card.get("name"),
                        "payload": card.get("name"),
                        # "payload": f"/SetSlots(current_card_name={card.get('name')}, current_card_number={card.get('number')})"
                    }
                )
            dispatcher.utter_message(response="utter_select_card", buttons=buttons)
        return events
