from pysh.dsl.pipeline import Command
from pysh.dsl.command import BaseSpec


class ShSpec(BaseSpec):
    """
    Runs a command via a shell.

    The first argument is the command to run, it'll be extended with
    the arguments expansion, so the shell can forward any extra arguments
    to it.

    >>> sh['ls']
    /bin/sh -e -c 'ls "$@"'

    >>> sh.jq['-c', foo]
    /bin/sh -e -c 'jq "$@"' -- -c '.field | @csv'

    Additionally, the first argument is scanned for `$variables` so
    they can be matched against the current locals/globals and exposed
    on the environment when running it.
    """
    def __init__(self):
        pass


class ShCommand(Command):

    def __getattribute__(self, name):
        """ Allows for ``sh.cat`` style shortcuts """
        # Once the first argument was given just forward to Command
        if self.args:
            return super().__getattribute__(name)

        clone = self.__copy__()
        clone.args.append(name)
        return clone
