from logger import Logger


class TuiLogger(Logger):
    def __init__(self):
        super().__init__()

    # Queue log messages without writing directly to stdout (Textual renders them).
    def log(self, msg, level=Logger.INFO, replaceLine=False):
        self.log_queue.put([level, replaceLine, msg.rstrip('\n').strip('\r')])
