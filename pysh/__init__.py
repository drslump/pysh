import os

from .version import __version__

# from .path import Path
from .env import Env

env = Env
# p = Path(spec='.')


def autoimport(locals, globals, name):
    import importlib
    if name in locals:
        return locals[name]
    if name in globals:
        return globals[name]

    try:
        return importlib.import_module(name)
    except ImportError:
        pass

    raise NameError(name)
