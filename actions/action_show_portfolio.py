from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.db import get_portfolio_options


class ActionShowPortfolio(Action):

    def name(self) -> str:
        return "action_show_portfolio"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: dict) -> list:
        # Retrieve the portfolio type from slots
        portfolio_type = tracker.get_slot("portfolio_type")

        # Placeholder for portfolio data
        portfolio_db = get_portfolio_options(tracker.sender_id)

        portfolio = [p.options for p in portfolio_db if p.type == portfolio_type]

        if portfolio:
            return [SlotSet("portfolio_options", portfolio[0])]
        else:
            return [SlotSet("portfolio_options", [])]