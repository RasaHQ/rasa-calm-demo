import random
import uuid

from locust import HttpUser, task


class RasaBotUser(HttpUser):
    """Load testing user that simulates interaction with a Rasa chatbot."""

    host = "http://localhost:5005"
    sender_id = None

    def on_start(self):
        """Initialize the user with a unique sender ID."""
        self.sender_id = str(uuid.uuid4())

    @task
    def send_check_balance(self):
        """Send a random 'check balance' message to the chatbot."""
        messages = [
            "check balance",
            "what is my balance",
            "can you tell me the balance",
            "please check balance",
            "what is the balance",
        ]
        self.send_message(random.choice(messages))

    def send_message(self, message: str):
        """Send a message to the chatbot and handle the response."""
        response = self.client.post(
            "/webhooks/rest/webhook",
            json={"sender": self.sender_id, "message": message},
            timeout=30,
        )
        if response.status_code != 200:
            print(
                f"Error sending message: {message}, "
                f"Status code: {response.status_code}, Content: {response.text}"
            )
