import logging
from typing import Dict, Text, Any, List, Optional
from rasa_sdk.types import DomainDict
from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher, Action
from importlib.metadata import version
import random
import os
from pydantic import BaseModel, HttpUrl, UUID4


class BankAPI(object):
    """Mock Bank API"""

    def __init__(self):
        self.cardholder_profiles = [
            {
                "name": "Maria Gonzalez",
                "replacement_eligibility": "is_eligible",
                "address_line_1": "300 Lakeside Ave",
                "address_line_2": "Unit 121",
                "city": "Seattle",
                "state": "WA",
                "postal_code": "98112",
                "country": "US",
                "days_since_card_sent": 5,
                "cards": [
                    {"name": "Gold Card", "number": "xxxx1"},
                    {"name": "Satin Card", "number": "xxxx3"},
                ],
            },
            {
                "name": "Stefan Müller",
                "replacement_eligibility": "is_eligible",
                "address_line_1": "Laemmleshalde 33",
                "address_line_2": "",
                "city": "Herrenberg",
                "state": "BV",
                "postal_code": "71083",
                "country": "DE",
                "days_since_card_sent": 15,
                "cards": [
                    {"name": "Silicon Card", "number": "xxxx1"},
                    {"name": "Family Card", "number": "xxxx4"},
                ],
            },
            {
                "name": "Mira Patel",
                "replacement_eligibility": "is_eligible",
                "address_line_1": "4 Church Walk",
                "address_line_2": "",
                "city": "Richmond",
                "state": "Surrey",
                "postal_code": "TW9 1SN",
                "country": "UK",
                "days_since_card_sent": 2,
                "cards": [
                    {"name": "Gold Card", "number": "xxxx1"},
                    {"name": "Kids Card", "number": "xxxx2"},
                    {"name": "Family Card", "number": "xxxx4"},
                ],
            },
            {
                "name": "David Benoit",
                "replacement_eligibility": "not_eligible_child",
                "address_line_1": "7 Rue de la Coudre",
                "address_line_2": "",
                "city": "Saint-Malo",
                "state": "Bretagne",
                "postal_code": "35400",
                "country": "FR",
                "days_since_card_sent": 35,
                "cards": [
                    {"name": "Kids Card", "number": "xxxx2"},
                ],
            },
        ]

    def select_random_cardholder_profile(self):
        # select a random cardholder profile
        profile = random.choice(self.cardholder_profiles)
        return profile

    def get_cardholder_by_name(self, name):
        # get a cardholder profile by name
        for profile in self.cardholder_profiles:
            if profile["name"] == name:
                return profile
        return None

    def get_all_cardholder_names(self):
        return [profile["name"] for profile in self.cardholder_profiles]
