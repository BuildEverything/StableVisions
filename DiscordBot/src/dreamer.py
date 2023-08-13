import json
import logging
from pathlib import Path

import openai

from world_state import WorldState


class Dreamer:
    def __init__(self, game_id, temperature):
        self.temperature = temperature
        self.model = "gpt-4-0613"
        self.explanation = None
        self.meta_information = None
        self.world_state_update = None
        self.world_state = WorldState(
            game_id,
            {
                'metadata': {
                    'player_information': {},
                    'world_system': {
                        'state': {
                            'phase': {
                                'current': 'init_party_building',
                            },
                        },
                        'rules': {
                            'character_creation': {},
                            'combat': {},
                            'magic': {},
                            'movement': {},
                            'social_interaction': {},
                            'travel': {},
                            'world_interaction': {},
                        },
                    },
                },
                'npcs': {},
                'monsters': {},
                'encounters': {},
                'items': {},
                'locations': {},
                'narrative': {
                    'story': {},
                    'emoji_associations': {},
                },
                'character_profiles': {},

            })
        self.message_to_players_header = None
        self.message_to_players = None

    def run(self, prompt, player_id):
        dreamer_guidebook = Path("src/dreamer_guidebook.md").read_text()
        self.world_state.load()

        messages = [
            {
                "role": "system",
                "content": f"You are the Dreamer, and AI which acts as a world architect, adjudicator, and Dungeon "
                           f"Master for tabletop RPGs. \n\n"
                           f"Here is the rulebook you should strictly follow:\n{dreamer_guidebook}.\n\n"
                           f"Here is the current world state as a JSON map: {json.dumps(self.world_state.state)}\n\n"
                           f"This is the player_id associated with the current input: {player_id}\n\n"
                           f"Here is the current input:\n\n{prompt}"
            }
        ]

        functions = [
            {
                "name": "run-dreamer-rp",
                "description": "Takes control of the dreamer, dictating the current game state "
                               "and making decisions on where the game should go next.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "explanation": {
                            "type": "string",
                            "description": "An explanation of the AI's decisions."
                        },
                        "meta_information": {
                            "type": "string",
                            "description": "Meta information about the game state in JSON format for debug purposes."
                        },
                        "world_state_update": {
                            "type": "string",
                            "description": "The world state is a document in a MongoDB database. world_state_update "
                                           "is an array of MongoDB update operations which will be applied to the "
                                           "world state document by referencing the MongoDB document ID, whose key is "
                                           "'__id' at the root of the document."
                        },
                        "message_to_players_header": {
                            "type": "string",
                            "description": "The header of the message which will be provided to players."
                        },
                        "message_to_players": {
                            "type": "string",
                            "description": "The text update which will be provided to players."
                        },
                    },
                    "required": ["explanation", "meta_information", "message"],
                },
            }
        ]

        response = openai.ChatCompletion.create(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            functions=functions,
            function_call={"name": "run-dreamer-rp"},
        )
        response_message = response["choices"][0]["message"]

        if not response_message.get("function_call"):
            logging.error("Error: expected function call in response message")
            self.explanation = "Error: expected function call in response message"
            self.meta_information = None
            self.message_to_players_header = "Error"
            self.message_to_players = "There was an error in the Dreamer's response. Please try again."
            return self.explanation, self.message_to_players_header, self.message_to_players

        function_args = json.loads(response_message["function_call"]["arguments"])

        self.explanation = function_args["explanation"]

        try:
            self.meta_information = json.loads(function_args["meta_information"])
        except json.JSONDecodeError:
            self.meta_information = None

        if "world_state_update" in function_args:
            try:
                self.world_state_update = function_args["world_state_update"]
                logging.info(f"World state update: {self.world_state_update}")
                self.world_state.update_state(self.world_state_update)
                self.world_state.save()
            except json.JSONDecodeError:
                self.world_state_update = None
        else:
            self.world_state_update = None

        self.message_to_players_header = function_args["message_to_players_header"]
        self.message_to_players = function_args["message_to_players"]


        return self.explanation, self.message_to_players_header, self.message_to_players
