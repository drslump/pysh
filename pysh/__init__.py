import os

from .version import __version__

# from .path import Path
from .env import Env

env = Env
# p = Path(spec='.')


class ExitStatusError(Exception):
    def __init__(self, status):
        self.status = status

# Override the constructor for the materialized classes
class ExitStatus_Error(ExitStatusError):
    status = None
    def __init__(self):
        assert type(self.status) is int

class ExitStatus0Error(ExitStatus_Error): status = 0
class ExitStatus1Error(ExitStatus_Error): status = 1
class ExitStatus2Error(ExitStatus_Error): status = 2
class ExitStatus3Error(ExitStatus_Error): status = 3
class ExitStatus4Error(ExitStatus_Error): status = 4
class ExitStatus5Error(ExitStatus_Error): status = 5
class ExitStatus6Error(ExitStatus_Error): status = 6
class ExitStatus7Error(ExitStatus_Error): status = 7
class ExitStatus8Error(ExitStatus_Error): status = 8
class ExitStatus9Error(ExitStatus_Error): status = 9

