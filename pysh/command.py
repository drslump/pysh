"""
command:
  - A factory for CommandSpec + CommandBuilder

CommandSpec:
  - Defines how a command must be called
  - Understands external commands and also pure python functions

CommandBuilder:
  - DSL interface for command construction
  - Each operation returns a cloned copy so stored references are immutable

CommandInvokation:
  - When a CommandBuilder is executed this object tracks it
  - Allows to access streams
  - Allows to query the exit status

"""

import re
from collections import Iterable
from pathlib import PurePath
from abc import abstractmethod, ABCMeta

from typing import Optional, Union, List, Any


def command(command, **kwargs):
    """
    Command factory. Returns a :class:`CommandBuilder` configured with a
    :class:`CommandSpec` suitable for the given command.

    Any additional keyword arguments will be provided to the matched concrete
    implementation of :class:`CommandSpec`.

    .. note:: Currently *command* can only be a path-like reference which
              refers to an external command, check :class:`ExternalCommandSpec`
              for additional details.
    """
    if isinstance(command, (str, PurePath)):
        spec = ExternalCommandSpec(command, **kwargs)
    else:
        #TODO: Support functions!
        raise RuntimeError('Only external commands are currently supported!')

    return CommandBuilder(spec)


class CommandSpec:  #TODO: (meta=ABCMeta) breaks?
    """
    Base abstract class for representing how a command should execute.

    Check :class:`ExternalCommandSpec` for a concrete implementation of the
    interface that allows to run external commands.
    """

    @abstractmethod
    def run(self, builder: 'CommandBuilder'):
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
        return 'Command({})'.format(self.command)


class ExternalCommandSpec(CommandSpec):
    """
    Implementation for external commands.

    Handles arguments according to the following rules:

    - keywords are always sorted to be reproducible
    - keywords always go before *positional* arguments
    - single char keywords get a ``-`` prefix (*shortpre* setting)
    - multi char keywords get a ``--`` prefix (*longpre* setting)
    - keywords starting with ``_`` are not prefixed (with *hyphenate* setting)
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
            return [pre + option]
        elif value in (False, None):
            return []

        if isinstance(value, str):
            value = [value]

        if self.repeat is False:
            return [option] + [v for v in value]  #XXX ignores valuepre in this case
        else:
            if self.repeat is not True:
                value = [self.repeat.join(value)]  #XXX custom repeat separator

            if self.valuepre:
                return [option + self.valuepre + v for v in value]
            else:
                return sum([[option, v] for v in value], [])  #XXX flattens the list

    def parse_args(self, *args, **kwargs) -> List[Any]:
        """

        """
        result = []
        for option in sorted(kwargs.keys()):
            value = kwargs[k]
            #TODO: We need to resolve value at this point to make repeated options reliable
            result.extend(self._parse_option(option, value))

        if self.argspre:
            result.append(self.argspre)

        #TODO: We need to resolve arg at this point
        for arg in args:
            if not isinstance(arg, Iterable):
                arg = [arg]

            result.extend(str(x) for x in arg)

        return result

    def run(self, builder: 'CommandBuilder'):
        raise NotImplementedError('sorry!')


class CommandBuilder:
    """
    .. automethod:: __or__
    .. automethod:: __ror__
    .. automethod:: __xor__
    .. automethod:: __le__
    .. automethod:: __ge__
    .. automethod:: __rshift__
    .. automethod:: __invert__
    """
    __slots__ = ('spec', 'args', 'no_raise', 'lazy_or', 'lazy_and')

    def __init__(self, spec: 'CommandSpec') -> None:
        self.spec = spec
        self.args = []
        self.lazy_or = self.lazy_and = None

        self.no_raise = [0]

    @property
    def stdin(self) -> bytes:  #TODO: how to model streams?
        return b''

    @property
    def stdout(self) -> bytes:  #TODO: how to model streams?
        return b''

    @property
    def stderr(self) -> bytes:  #TODO: how to model streams?
        return b''

    def __copy__(self) -> 'CommandBuilder':
        clone = type(self)(self.spec)
        clone.args = list(self.args)
        clone.no_raise = list(self.no_raise)
        clone.lazy_and = self.lazy_and
        clone.lazy_or = self.lazy_or
        return clone

    def __repr__(self):
        return '<{} {}>'.format(self.spec.command, ' '.join(self.args))

    def __getitem__(self, key) -> 'CommandBuilder':
        """ Slice access records arguments almost in verbatim form, however
            there is splitting on whitespace so if you want to pass an argument
            containing whitespace it needs to be escaped with backslash.
        """
        if isinstance(key, slice):
            raise NotImplementedError()

        clone = self.__copy__()

        args = re.split(r'(?<!\\)\s', key)
        for arg in args:
            if arg == '' or arg.isspace():
                continue
            arg = re.sub(r'\\(\s)', r'\1', arg)  # unescape white space
            clone.args.extend(self.spec.parse_args(arg))

        return clone

    def __call__(self, *args, **kwargs) -> 'CommandBuilder':
        clone = self.__copy__()
        clone.args.extend(
            self.spec.parse_args(*args, **kwargs)
        )
        return clone

    def invoke(self) -> 'CommandInvocation':
        """ Executes the command as currently configured

            XXX .invoke launch the process and returns immediatly the invocation object.
                Autoexpr calls it with .wait() so its syncronous. exec is the explicit
                equivalent to autoexpr
        """
        return CommandInvocation(self)

    def pipe(self, stdout=None, stderr=None) -> 'CommandBuilder':
        #TODO: implement it :)
        return self.__copy__()

    def to_status(self) -> int:
        result = self.invoke()
        assert isinstance(result, int)
        return result.status

    def to_binary(self) -> bytes:
        result = self.invoke()
        return result.stdout

    def to_text(self) -> str:
        result = self.invoke()
        return result.stdout.decode('utf-8')

    def catch(self, *statuses, **kwargs) -> 'CommandBuilder':
        """ Avoids raising upon given status codes. If no statuses are provided
            then it'll catch all of them.

            grep['foo'].catch()   # ignore any exit status
            grep['foo'].catch(1)  # ignore exit status 1
            grep['foo'].catch(1, 3)  # ignore exit status 1 or 3
            grep['foo'].catch(*range(1, 10))  # ignore status 1-9

            grep['foo'].catch(errcho('foo'))  # echo for all
            grep['foo'].catch(1, _2=echo('foo'))  # ignore 1, 2 echos

            grep['foo'].catch(
                _0 = echo('found'),        # 0 (even if it doesn't raise)
                _1_2 = echo('error'),      # 1,2
                _1__4 = echo('error'),      # 1,2,3,4 echo
                _10 = echo('error') and exit(1),   # 10 echoes and returns 1 to the pipe
                __10 = echo('<=10'),
                10__ = echo('>=10'),
                _ = exit(1, 'not found!')  # else
            )

            grep['foo'].catch(lambda p: print(p.status))

            grep['foo'].catch(signals=signals.SIGHUP)
            grep['foo'].catch(SIGHUP=None, SIGUSR2=echo('received!'))
            grep['foo'].catch(0, SIGHUP=None)
            grep['foo'].catch(0, -signals.SIGHUP)
            #TODO: maybe a method called .trap() like bash?
        """

        clone = self.__copy__()
        if not statuses:
            statuses = tuple(range(256))
        clone.no_raise = statuses
        return clone

    def and_then(self, callable):
        clone = self.__copy__()
        clone.lazy_and = callable
        return clone

    def or_else(self, callable):
        clone = self.__copy__()
        clone.lazy_or = callable
        return clone

    def __invert__(self) -> 'CommandBuilder':
        """ :ref:`Reckless: ~`
        """
        return self.pipe(stderr=null).catch()

    def __or__(self, rhs) -> 'CommandBuilder':
        """ :ref:`Pipe: |`
        """
        if isinstance(rhs, CommandBuilder):
            return self.pipe(rhs)
        else:
            return rhs(self)

    def __ror__(self, lhs) -> 'CommandBuilder':
        """ Reverse for :meth:`__or__` to handle ``value | command``.
        """
        #TODO: lhs should be injected into stdin
        raise RuntimeError('Unsupported <any> | <cmd>')

    def __xor__(self, rhs) -> 'CommandBuilder':
        """ :ref:`Piperr: ^ 🚧`

            TODO: This doesn't compose well with redirection `>` which has
            a lower precendence than ^. So `cmd > fname ^ null` would be
            evaled as `cmd > (fname ^ null)`.
            If we the error reported on path/string ^ something is not too
            bad then it's just a matter of training the user to redirect
            always first the stderr.
        """
        return self.pipe(stderr=rhs)

    def __gt__(self, other) -> 'CommandBuilder':
        """ :ref:`Redirection: >`
        """
        assert not isinstance(other, CommandBuilder)
        return self.pipe(other)

    def __lt__(self, other):
        """ Reverse for :meth:`__gt__` to handle ``value < command``
        """
        assert not isinstance(other, CommandBuilder)
        raise RuntimeError('`val < cmd` not implemented yet')

    def __le__(self, other):
        """ :ref:`Lazy application: <= 🚧`
        """
        return self(other)

    def __ge__(self, other):
        """ Reverse for :meth:`__le__` to handle ``func <= command``
        """
        return other(self)

    def __rshift__(self, rhs):
        """ :ref:`Appending Redirection: >>`
        """
        assert not isinstance(rhs, CommandBuilder)
        raise RuntimeError('`cmd >> val` not implemented yet')

    def __lazybooland__(self, rhs_callable):
        """ Lazy boolean protocol for ``and``.

            .. note:: This is a non-standard protocol from the lazybools transform.
        """
        return self.and_then(rhs_callable)

    def __lazyboolor__(self, rhs_callable):
        """ Lazy boolean protocol for ``or``.

            .. note:: This is a non-standard protocol from the lazybools transform.
        """
        return self.or_else(rhs_callable)

    def __lazyboolnot__(self):
        """ Lazy boolean protocol for ``not``.

            Raises an error, not possible to negate a command.

            .. note:: This is a non-standard protocol from the lazybools transform.
        """
        raise SyntaxError('a command cannot be negated')

    def __int__(self):
        return self.to_status()

    def __bytes__(self):
        return self.to_binary()

    def __str__(self):
        return self.to_text()


class CommandInvocation:
    __slots__ = ('command', 'status', 'stdin', 'stdout', 'stderr')

    def __init__(self, command: CommandBuilder) -> None:
        self.command = command
        self.status: Optional[int] = None
        self.stdout = b''
        self.stderr = b''

    def wait(self):
        """ Block until the command terminates.
        """

    def __repr__(self):
        return '{!r}()'.format(self.command)


class ShCommandSpec(CommandSpec):
    """ Runs a command via a shell.

        The first argument is the command to run, it'll be extended with
        the arguments expansion, so the shell can forward any extra arguments
        to it.

            sh['ls']
            # /bin/sh -e -c 'ls "$@"'

            jq['-c', foo]
            # /bin/sh -e -c 'jq "$@"' -- -c '.field | @csv'

        Additionally, the first argument is scanned for `$variables` so
        they can be matched against the current locals/globals and exposed
        on the environment when running it.
    """

    def __init__(self):
        pass


class ShCommandBuilder(CommandBuilder):

    def __getattribute__(self, name):
        """ Allows for ``sh.cat`` style shortcuts """
        # Once the first argument was given just forward to CommandBuilder
        if self.args:
            return super().__getattribute__(name)

        clone = self.__copy__()
        clone.args.append(name)
        return clone



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



