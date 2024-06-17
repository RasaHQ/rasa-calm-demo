from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher


class ActionAuthenticateUser(Action):

    def name(self) -> str:
        return "action_authenticate_user"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: dict) -> list:
        # Retrieve the user credentials from slots
        user_name = tracker.get_slot("user_name")
        user_password = tracker.get_slot("user_password")

        # Dummy authentication.
        # Placeholder for user authentication, in real scenarios the username and
        # password should be checked against a database.
        authenticated = True

        if authenticated:
            return [SlotSet("is_user_logged_in", True)]
        else:
            return [SlotSet("is_user_logged_in", False)]