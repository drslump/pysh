import os

from .version import __version__

from .path import PathWrapper
from .env import Env
from .command import ShCommandBuilder, ShCommandSpec


# Prelude for scripts
__all__ = [
    '_', 'PWD',
    'ENV',
    # Augmented at the bottom for all the Exit stuff
]


ENV = Env()
_ = PWD = PathWrapper()

sh = ShCommandBuilder(ShCommandSpec())


# TODO: Perhaps the ABC module can be used to replace the __new__ code
class ExitError(Exception):
    """ Represents an exit status error after running a command.

        There are a number of predefined ones named ``ExitErrorN``, where N is a
        number matching the desired exit status. Additionally ``ExitN`` are *ready
        to raise* instances of those errors.
    """

    def __new__(cls, *args, **kwargs):
        """ Control the creation of these classes so we can intantiate a concrete
            one if available. This allows for except blocks to capture a specific
            error no matter if it was raised from the generic or the specific one.
        """
        if cls is ExitError:
            concrete = globals().get('Exit{}Error'.format(args[0]))
            if concrete:
                return super().__new__(concrete)

        return super().__new__(cls)

    def __init__(self, status, message=None):
        self.status = status
        self.message = message

    def __repr__(self):
        return '<ExitError:{}>'.format(self.status)

    def __str__(self):
        if self.message:
            return 'Exit:{}: {}'.format(self.status, self.message)
        else:
            return 'Exit:{}'.format(self.status)


class _ExitError(ExitError):
    """ Private class so we override the constructor for the specialized.
    """
    def __init__(self, status_or_message=None, message=None):
        #hack: workaround __new__ sending the status from ExitError
        if status_or_message != self.status and message is None:
            message = status_or_message

        super().__init__(self.status, message)


# Some common statuses have specialized version
class Exit0Error(_ExitError): status = 0
class Exit1Error(_ExitError): status = 1
class Exit2Error(_ExitError): status = 2
class Exit3Error(_ExitError): status = 3
class Exit4Error(_ExitError): status = 4
class Exit5Error(_ExitError): status = 5
class Exit6Error(_ExitError): status = 6
class Exit7Error(_ExitError): status = 7
class Exit8Error(_ExitError): status = 8
class Exit9Error(_ExitError): status = 9

# Also some default instances to raise around when no message is needed
Exit0 = Exit0Error()
Exit1 = Exit1Error()
Exit2 = Exit2Error()
Exit3 = Exit3Error()
Exit4 = Exit4Error()
Exit5 = Exit5Error()
Exit6 = Exit6Error()
Exit7 = Exit7Error()
Exit8 = Exit8Error()
Exit9 = Exit9Error()


# Augment the prelude with all the Exit stuff
__all__.extend(k for k in globals() if k.startswith('Exit'))
