"""
command:
  - A factory for a Command with a concrete BaseSpec

BaseSpec (and concrete classes):
  - Defines how a command must be called
  - Understands external commands and also pure python functions

Expr:
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

from pysh.path import Path

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
        #TODO: According to PEP468 since 3.6 keywords order is preserved
        for option in sorted(kwargs.keys()):
            value = kwargs[option]
            #TODO: We need to resolve value at this point to make repeated options reliable
            result.extend(self._parse_option(option, value))

        if self.argspre:
            result.append(self.argspre)

        #TODO: We need to resolve arg at this point
        for arg in args:
            if isinstance(arg, str) or not isinstance(arg, Iterable):
                arg = [arg]

            result.extend(str(x) for x in arg)

        return result

    def run(self, builder: 'Command'):
        raise NotImplementedError('sorry!')


class Expr:  #TODO: breaks?? (meta=ABCMeta):
    """
    Base class for DSL expression builders.

    .. automethod:: __or__
    .. automethod:: __ror__
    .. automethod:: __xor__
    .. automethod:: __le__
    .. automethod:: __ge__
    .. automethod:: __rshift__
    .. automethod:: __invert__
    """
    def invoke(self) -> 'Invocation':
        """ Executes the command as currently configured

            XXX .invoke launch the process and returns immediatly the invocation object.
                Autoexpr calls it with .wait() so its syncronous. exec is the explicit
                equivalent to autoexpr
        """
        return Result(self)

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

    def pipe(self, stdout=None, *, stderr=None) -> Union['Pipe', 'Piperr']:
        """ Explicit interface for the ``|`` and ``^`` operators.
        """
        result = self.__copy__()
        if stderr is not None:
            result = result ^ stderr
        if stdout is not None:
            result = result | stdout

        return result

    def __gt__(self, other) -> 'Redirect':
        """ :ref:`Redirection: >`
        """
        if isinstance(other, Expr):
            return NotImplemented

        #TODO: support callables
        if not isinstance(other, (IOBase, str, bytes, PurePath, Path)):
            return NotImplemented

        print('{!r} __GT__ {!r}'.format(self, other))

        return Redirect(self, other)

    def __lt__(self, other) -> 'Redirect':
        # Not possible to redirect to an expression?
        return NotImplemented

    def __rshift__(self, rhs) -> 'Redirect':
        """ :ref:`Appending Redirection: >>`
        """
        assert not isinstance(rhs, Command)
        return Redirect(self, rhs, appending=True)

    def __or__(self, rhs) -> 'Pipe':
        """ :ref:`Pipe: |`
        """
        if not isinstance(rhs, Expr):
            return NotImplemented

        return Pipe(self, rhs)

    def __ror__(self, lhs) -> 'Pipe':
        """ Reverse for :meth:`__or__` to handle ``value | command``.
        """
        if not isinstance(lhs, Expr):
            #TODO: lhs should be injected into stdin
            return NotImplemented

        return Pipe(lhs, self)

    def __xor__(self, rhs) -> 'Piperr':
        """ :ref:`Piperr: ^ 🚧`
        """
        # Prefer right associative if it has the reverse (precedence transform)
        if hasattr(rhs, '__rxor__'):
            return rhs.__rxor__(self)

        return Piperr(self, rhs)

    def __invert__(self) -> 'Reckless':
        """ :ref:`Reckless: ~`
        """
        return Reckless(self)

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


class Command(Expr):
    """
    .. automethod:: __lshift__
    .. automethod:: __rshift__
    """
    __slots__ = ('spec', 'args', 'no_raise',)

    def __init__(self, spec: 'BaseSpec') -> None:
        self.spec = spec
        self.args = []

        self.no_raise = [0]

    def __copy__(self) -> 'Command':
        clone = type(self)(self.spec)
        clone.args = list(self.args)
        clone.no_raise = list(self.no_raise)
        return clone

    def __repr__(self):
        cmd = '{} {}'.format(self.spec.command, ' '.join(self.args))
        return '`{}`'.format(cmd.strip())

    def __getitem__(self, key) -> 'Command':
        """ Slice access records arguments almost in verbatim form, however
            there is splitting on whitespace so if you want to pass an argument
            containing whitespace it needs to be escaped with backslash.
        """
        if isinstance(key, slice):
            raise NotImplementedError()

        clone = self.__copy__()

        #TODO: detect paths/globs and create PathWrapper instances as args

        args = re.split(r'(?<!\\)\s', key)
        for arg in args:
            if arg == '' or arg.isspace():
                continue
            arg = re.sub(r'\\(\s)', r'\1', arg)  # unescape white space
            clone.args.extend(self.spec.parse_args(arg))

        return clone

    def __call__(self, *args, **kwargs) -> 'Command':
        clone = self.__copy__()
        clone.args.extend(
            self.spec.parse_args(*args, **kwargs)
        )
        return clone

    def io(self, encoding=None, *, stdin=None, stdout=None, stderr=None):
        # encoding: applies to all
        # TODO: Shall it apply to commands only? or belongs to Expr?
        # TODO: buffering stuff to be defined, too many variables, no need
        #       to expose everything, we need sensible defaults with a clear
        #       explanation. Probably the best approach would be to allow to
        #       define them as part of the CommandSpec since buffering is
        #       usually command specific.
        pass

    def catch(self, *statuses, **kwargs) -> 'Command':
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

        # TODO: Shall it apply to commands only? or belongs to Expr?

        clone = self.__copy__()
        if not statuses:
            statuses = tuple(range(256))
        clone.no_raise = statuses
        return clone

    def  __lshift__(self, other) -> 'Command':
        """ :ref:`Application: << 🚧`
        """
        return self(other)

    def __rlshift__(self, other) -> 'Command':
        """ Reverse for :meth:`__lshift__` to handle ``func << command``
        """
        if not callable(other):
            return NotImplemented

        return other(self)

    def __int__(self):
        return self.to_status()

    def __bytes__(self):
        return self.to_binary()

    def __str__(self):
        return self.to_text()


class Pipe(Expr):
    """
    Represents a pipe ``|`` operation.
    """
    def __init__(self, lhs: Expr, rhs: Expr) -> None:
        self.lhs = lhs
        self.rhs = rhs

    def __repr__(self):
        return '({!r} | {!r})'.format(self.lhs, self.rhs)


class Piperr(Pipe):
    """
    Represents a piperr ``^`` operation.
    """
    def __repr__(self):
        rhs = self.rhs.name if isinstance(self.rhs, IOBase) else repr(self.rhs)
        return '({!r} ^ {})'.format(self.lhs, rhs)


class Redirect(Expr):
    """
    Represents a redirection ``>`` or ``>>`` operation.
    """
    def __init__(self, lhs: Expr, rhs: Union[Path], *, appending=False) -> None:
        self.lhs = lhs
        self.rhs = rhs
        self.appending = appending

    def __repr__(self):
        op = '>>' if self.appending else '>'
        rhs = self.rhs.name if isinstance(self.rhs, IOBase) else repr(self.rhs)
        return '({!r} {} {})'.format(
            self.lhs, op, rhs)


class Reckless(Expr):
    """
    Represents the reckless operator ``~``
    """
    def __init__(self, expr: Expr) -> None:
        self.expr = expr

    def __repr__(self):
        return '~{!r}'.format(self.expr)


class Application(Expr):
    """
    TODO: Not needed?

    Represents the application operator ``<<``

    .. TODO:: ``foo <= bar > null`` is evaled as ``foo(bar) > null``

    Maybe it's best to use a ``<<`` as application operator, that
    allows to have an eager one:

        sh << ' ... ' > null  # sh('...') > null

    and also a lazy one that should work for most use cases:

        fork <<= grep['foo'] > null  # fork(grep['foo'] > null)

    the drawback is that the following is not valid syntax:

        fork(n=8) <<= cmd > null  # cannot assign to a call expression

    that might be solved with a lexer transform but it feels dirty:

        __1 = fork(n=8); __1 <<= cmd > null

    or by forcing the user to change the expression to:

        fork(n=8).fn <<= cmd > null

    but then operator are also NOT allows:

        cat | xargs(n=1) <<= cmd > null

    so the only ergonomic solution seems to be the lexer transformation:

        cat | xargs(n=1) << (cmd > null)

    although for the time being, experiment with the explicit version:

        runner = cat | xargs(n=1)
        runner <<= cmd > null

    TODO !!IMPORTANT:
        Perhaps the simpler way is to forget about this lazy application
        altogether and bring it more to Python for this advanced use cases.

        >>> cat | xargs(foo | bar, n=1) > null
        >>> cat | xargs(  # my favorite I think
        >>>     n=1,
        >>>     expr= foo | bar
        >>> ) > null
        >>> cat | xargs(n=1)[
        >>>    foo | bar
        >>> ] > null
        >>> cat | xargs(n=1) << (foo | bar) > null

        In practice any flow-control command will probably need to have a
        custom implementation and if so it can use existing mechanisms to
        provide a convenient syntax.

        If anything, the ``<<=`` seems like the best fit, since it should
        allow something like:

        >>> results.txt < xargs(-n) <<= foo | bar

        which looks quite bad to be honest, it might be useful for a ``time``
        style command, that doesn't need to handle the output:

        >>> time <<= foo | bar

        but even then, it's not so common as to justify having such a complex
        operator. If we get rid of lazy application we can just simplify the
        precedence transform so it only operates over ``>`` and ``<``.

    """
    def __init__(self, lhs: Command, rhs: Any) -> None:
        self.lhs = lhs
        self.rhs = rhs

    def __repr__(self):
        return '({!r} << {!r})'.format(self.lhs, self.rhs)


class Result:
    __slots__ = ('expr', 'status', 'stdin', 'stdout', 'stderr')

    def __init__(self, expr: Expr) -> None:
        self.expr = expr
        self.status: Optional[int] = None
        self.stdout = b''
        self.stderr = b''

    def wait(self):
        """ Block until the command terminates.
        """

    def __repr__(self):
        return 'Result{{{!r}}}'.format(self.expr)


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



