"""
command:
  - A factory for a Command with a concrete BaseSpec

BaseSpec (and concrete classes):
  - Defines how a command must be called
  - Understands external commands and also pure python functions

Pipeline:
  - Base class for all builders.
  - Each operation returns a cloned copy so stored references are immutable

Command:
  - DSL interface for command construction

Pipe, Redirect:
  - Expression represent an operation

Result:
  - When a Expr is executed this object tracks it
  - Allows to access streams
  - Allows to query the exit status


TODO: check http://harp.pythonanywhere.com/python_doc/library/concurrent.html
      for launching python commands

"""

import re
from collections import Iterable
from pathlib import PurePath
from abc import abstractmethod, ABCMeta
from io import IOBase

from pysh.dsl.path import Path
from pysh.dsl.pipeline import Command, Pipeline

from typing import Optional, Union, List, Callable, Any


def command(command, **kwargs):
    """
    Command factory. Returns a :class:`Command` configured with concreate
    implementation of :class:`BaseSpec` suitable for the given command.

    Any additional keyword arguments will be provided to the implementation
    of :class:`Spec`.

    .. note:: Currently *command* can only be a path-like reference which
              refers to an external command, check :class:`ExternalSpec` for
              additional details.
    """
    if isinstance(command, (str, PurePath)):
        spec = ExternalSpec(command, **kwargs)
    else:
        #TODO: Support functions!
        raise RuntimeError('Only external commands are currently supported!')

    return Command(spec)



class BaseSpec:  #TODO: (meta=ABCMeta) breaks?
    """
    Base abstract class for representing how a command should execute.

    Check :class:`ExternalSpec` for a concrete implementation of the
    interface that allows to run external commands.
    """

    @abstractmethod
    def run(self, builder: 'Command'):
        """
        This is a somewhat internal method to execute a builder according to
        the spec. It's intended to be used by :meth:`CommandBuilder.invoke`.
        """

    @abstractmethod
    def parse_args(self, *args, **kwargs) -> List[Any]:
        """
        Used by :meth:`CommandBuilder` call and slicing protocols to convert
        their received values into arguments according to the spec.

        .. TODO:: Does it belong in the interface? shouldn't it be part of External?
        """

    def __repr__(self):
        return '{}({})'.format(self.__class__.name, self.command)


class ExternalSpec(BaseSpec):
    """
    Implementation for external commands.

    Handles arguments according to the following rules:

    - keywords always go before *positional* arguments except for ``_``
    - single char keywords get a ``-`` prefix (*shortpre* setting)
    - multi char keywords get a ``--`` prefix (*longpre* setting)
    - keywords starting with ``_`` are not prefixed (with *hyphenate* setting)
    - keyword ``_`` can contain *positional arguments*
    - ``an_option`` -> ``an-option`` (*hyphenate* setting)
    - *False* and *None* values for keywords don't produce an option
    - when *argspre* is set it's used before the positional arguments
    - keyword values produce an additional argument (*valuepre* setting)
    - iterables get expanded, repeating keyword if *repeat* is *True* or
      joining them with the value of *repeat* if it's a string. When *repeat*
      is *False* additional arguments are placed after the option.
    """
    __slots__ = ('command', 'ok_status', 'hyphenate', 'repeat', 'shortpre', 'longpre', 'valuepre', 'falsepre', 'argspre')

    def __init__(self, command: str, *,
                 ok_status=(0,), hyphenate=True, repeat: Union[bool,str] = True,
                 shortpre='-', longpre='--',
                 valuepre: Optional[str] = None, argspre: Optional[str] = None):
        self.command = command
        self.ok_status = tuple([ok_status]) if isinstance(ok_status, int) else ok_status
        self.hyphenate = hyphenate
        self.shortpre = shortpre
        self.longpre = longpre
        self.valuepre = valuepre
        self.argspre = argspre
        self.repeat = repeat

    def _parse_option(self, option, value) -> List[str]:
        if self.hyphenate:
            option = option.replace('_', '-')

        is_short = 1 == len(option)
        if not option.startswith('-'):
            option = (self.shortpre if is_short else self.longpre) + option

        if value is True:
            return [option]
        elif value in (False, None):
            return []

        if isinstance(value, str) or not isinstance(value, Iterable):
            value = [value]

        if self.repeat is False:
            return [option] + [str(v) for v in value]  #XXX ignores valuepre in this case
        else:
            if self.repeat is not True:
                value = [self.repeat.join(str(v) for v in value)]  #XXX custom repeat separator

            if self.valuepre:
                return [option + self.valuepre + str(v) for v in value]
            else:
                return sum([[option, str(v)] for v in value], [])  #XXX flattens the list

    def parse_args(self, *args, **kwargs) -> List[Any]:
        """

        """
        result = []
        # since Python 3.6 keywords order is preserved
        for option in kwargs.keys():
            value = kwargs[option]

            if option == '_':
                args = list(args)
                args.append(value)
                continue

            #TODO: We need to resolve value at this point to make repeated options reliable
            result.extend(self._parse_option(option, value))

        #TODO: Output only once for run of arguments (and only if one of them starts with shortpre or longpre)
        if self.argspre:
            result.append(self.argspre)

        #TODO: We need to resolve arg at this point
        for arg in args:
            if isinstance(arg, str) or not isinstance(arg, Iterable):
                arg = [arg]

            result.extend(str(x) for x in arg)

        return result

    def get_args_for(self, builder: 'Command'):
        args = []
        for arg in builder.args:
            if type(arg) == tuple:
                positional, keywords = arg
                args.extend(self.parse_args(*positional, **keywords))
            else:
                args.extend(self.parse_args(arg))
        return args

    def run(self, builder: 'Command'):
        raise NotImplementedError('sorry!')




class Result:
    __slots__ = ('expr', 'status', 'stdin', 'stdout', 'stderr')

    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline
        self.status: Optional[int] = None
        self.stdout = b''
        self.stderr = b''

    def wait(self):
        """ Block until the command terminates.
        """

    def __repr__(self):
        return 'Result{{{!r}}}'.format(self.pipeline)




### ----------

class LazyEnvInterpolator:

    @staticmethod
    def get_frame_vars(back_cnt=2):
        """ Helper to obtain the variables from the scope of a calling frame
        """
        import inspect
        from collections import ChainMap

        frame = inspect.currentframe()
        try:
            while back_cnt:
                back_cnt -= 1
                frame = frame.f_back

            return ChainMap(frame.f_locals, frame.f_globals)
        finally:
            del frame  # make sure we avoid circular references with the stack


    def __init__(self, tpl, vars):
        self.tpl = tpl
        self.vars = vars

    def get_variable_names(self):
        pattern = r'\$\{?([A-Za-z][A-Za-z0-9_]*)'
        return [
            m.group(1)
            for m in re.finditer(pattern, self.tpl)
            ]
