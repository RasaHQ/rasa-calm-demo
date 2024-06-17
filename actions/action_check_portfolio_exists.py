from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.db import get_portfolio_options


class ActionCheckPortfolioExists(Action):

    def name(self) -> str:
        return "action_check_portfolio_exists"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: dict) -> list:
        # Retrieve the portfolio type from slots
        portfolio_type = tracker.get_slot("portfolio_type")

        portfolio_db = get_portfolio_options(tracker.sender_id)

        portfolio_exists = [p for p in portfolio_db if p.type == portfolio_type]

        if portfolio_exists:
            return [SlotSet("portfolio_exists", True)]
        else:
            return [SlotSet("portfolio_exists", False)]