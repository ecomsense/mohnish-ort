class Options:

    def __init__(self):
        self.status = 0
        self.buy_id = 0
        self.buy_params = {}
        self.short_id = 0
        self.short_params = {}


class Calls(Options):

    def __init__(self):
        super().__init__()


class Puts(Options):

    def __init__(self):
        super().__init__()


if __name__ == "__main__":
    c = Calls()
    print(c.status)
