class EventDispatcher:
    def __init__(self, handler):
        self.handler = handler

    def dispatch(self, event):
        self.handler(event)
