class TerminalError(Exception):
    """This stops the entire program (after logging the error)
    Use this for network and proxy errors
    """

    pass


class NonTerminalError(Exception):
    """Stops processing the domain and move on to the next"""

    pass
