import math
import random
import sys


class InputHandler:
    def __init__(self):
        self.valid_args = {
            'w': 'width',
            'h': 'height',
            'width': 'width',
            'height': 'height',
            's': 'seed',
            'seed': 'seed',
            'lucid': 'lucid',
            'steps': 'steps',
            'g': 'guidance_scale',
            'guidance_scale': 'guidance_scale',
            'num_images': 'num_images',
            'n': 'num_images',
            'negative_prompt': 'negative_prompt',
            'frames': 'num_frames',
            'f': 'num_frames',
        }

    def sanitize_input(self, message):
        split_message = message.split('--')
        prompt = split_message[0].strip()

        options_map = {}
        for arg in split_message[1:]:
            split_arg = arg.strip().split(' ', 1)
            if len(split_arg) > 1:
                translated_arg = self.translate_arg(split_arg[0])

                if translated_arg is not None:
                    options_map[split_arg[0]] = split_arg[1]
            else:
                options_map[split_arg[0]] = None

        if 'seed' not in options_map:
            options_map['seed'] = random.Random().randint(0, sys.maxsize)

        return prompt, options_map

    def translate_arg(self, arg_name: str) -> str:
        arg_name = arg_name.lower()
        if arg_name in self.valid_args:
            return self.valid_args[arg_name]

        return None
