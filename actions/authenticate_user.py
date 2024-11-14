from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
import logging

logger = logging.getLogger(__name__)

class ActionAuthenticateUser(Action):

    def name(self) -> str:
        return "action_authenticate_user"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: dict) -> list:
        logger.info("Executing action_authenticate_user")
        # Retrieve the user credentials from slots
        user_name = tracker.get_slot("user_name")
        user_password = tracker.get_slot("user_password")
        attempts = tracker.get_slot("login_failed_attempts")
        if not attempts:
            attempts = 0

        # Dummy authentication.
        # Placeholder for user authentication, in real scenarios the username and
        # password should be checked against a database.
        authenticated = not (user_name == "John" and user_password == "1234")

        if authenticated:
            return [SlotSet("is_user_logged_in", True)]
        else:
            return [SlotSet("is_user_logged_in", False), SlotSet("login_failed_attempts", attempts + 1)]
