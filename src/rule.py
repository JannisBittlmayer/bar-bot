class Rule:
    def __init__(self, strings_to_match, callback):
        self.strings_to_match = strings_to_match
        self.callback = callback
