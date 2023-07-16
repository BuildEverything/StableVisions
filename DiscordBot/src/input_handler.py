class InputHandler:

    def sanitize_input(self, message):
        split_message = message.split('--')
        prompt = split_message[0].strip()
        user_args = ['--' + arg.strip() for arg in split_message[1:]]
        return prompt, user_args

    def process_args(self, user_args):
        allowed_args = ['--W', '--H', '--seed']
        validated_args = [arg for arg in user_args if any(allowed_arg in arg for allowed_arg in allowed_args)]
        return validated_args
