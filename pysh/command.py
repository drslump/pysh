"""
TODO: check http://harp.pythonanywhere.com/python_doc/library/concurrent.html
      for launching python commands

TODO: Check http://www.pixelbeat.org/programming/sigpipe_handling.html
"""

import re
from collections import Iterable
from pathlib import PurePath
from io import IOBase

from pysh.dsl import Path, Command, Pipeline, BaseSpec

from typing import Optional, Union, List, Tuple, Dict, Callable, Any, cast


def command(*commands: str, **kwargs: Any) -> Union[Command, List[Command]]:
    """
    Command factory. Returns a :class:`pysh.dsl.Command` configured with
    a concrete implementation of :class:`BaseSpec` suitable for the given command.

    Any additional keyword arguments will be provided to the implementation of
    :class:`Spec`.

    When multiple commands are given they are all created and returned in a tuple
    respecting the given order. This allows to easy bootstrap a bunch of them with
    unpacking.

    .. note:: Currently *command* can only be a path-like reference which refers to
              an external command, check :class:`ExternalSpec` for additional details.
    """
    assert len(commands) >= 1, 'Expected at least one command'

    results: List[Command] = []
    for command in commands:
        if isinstance(command, (str, PurePath)):
            spec = ExternalSpec(command, **kwargs)
        else:
            #TODO: Support functions!
            raise RuntimeError('Only external commands are currently supported!')

        results.append(Command(spec))

    if len(results) == 1:
        return results[0]
    else:
        return results



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
                 valuepre: Optional[str] = None, argspre: Optional[str] = None) -> None:
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
                repeat = cast(str, self.repeat)  #XXX help mypy
                value = [repeat.join(str(v) for v in value)]  #XXX custom repeat separator

            if self.valuepre:
                return [option + self.valuepre + str(v) for v in value]
            else:
                return sum([[option, str(v)] for v in value], [])  #XXX flattens the list

    def parse_args(self, positional, keyword) -> List[Any]:
        """

        """
        result = []
        # since Python 3.6 keyword order is preserved
        for option, value in keyword.items():
            if option == '_':
                positional = list(positional)
                positional.append(value)
                continue

            #TODO: We need to resolve value at this point to make repeated options reliable
            result.extend(self._parse_option(option, value))

        #TODO: Output only once for run of arguments (and only if one of them starts with shortpre or longpre)
        if self.argspre:
            result.append(self.argspre)

        #TODO: We need to resolve arg at this point
        for arg in positional:
            if isinstance(arg, str) or not isinstance(arg, Iterable):
                arg = [arg]

            result.extend(str(x) for x in arg)

        return result

    def get_args_for(self, builder: 'Command'):
        args = []
        for arg in builder._args:
            args.extend(self.parse_args(arg.positional, arg.keywords))
        return args

    def run(self, builder: 'Command'):
        raise NotImplementedError('sorry!')

    def __repr__(self):
        return '{}{{{}}})'.format(self.__class__.__name__, self.command)





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



class ShSpec(ExternalSpec):
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
