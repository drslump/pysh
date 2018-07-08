from collections import ChainMap
from os import environ


class Env:
    """
    Represents environment variables.

    It's a bit tricky right now because we don't have a clear model for the task
    execution. Ideally an env is a customization of the parent env, which can
    shadow its parent variables and restore its values when it's done.
    """
    __slots__ = ('vars', 'saved')

    def __init__(self, **kwargs):
        #TODO: a None value should mean that it's not preset
        self.vars = kwargs
        self.saved = {}

    def __enter__(self):
        # upon entering a with-block we want to apply to the environ
        # any shadow vars we might have
        for k,v in self.vars.items():
            self[k] = v

    def __exit__(self, exc_type, exc_value, traceback):
        for k,v in self.saved.items():
            if v is None:
                del environ[k]
            else:
                environ[k] = v

    def __getitem__(self, name):
        name = name.upper()
        if name in self.vars:
            return self.vars[name]
        return environ[name]

    def __setitem__(self, name, value):
        name = name.upper()

        if name not in self.saved:
            self.saved[name] = environ.get(name)

        self.vars[name] = value
        environ[name] = value

    #TODO: expose getattr/setattr for use: env.FOO

    def __call__(self, **kwargs):
        """ Use: env(foo=1, bar=2)
        """
        return Env(**kwargs)
