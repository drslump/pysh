"""

#TODO: Check http://www.pixelbeat.org/programming/sigpipe_handling.html
"""

import re
from io import IOBase
from pathlib import PurePath

from pysh.dsl.path import Path

from typing import Optional, Union, List, Callable, Any


class Pipeline:  #TODO: breaks?? (meta=ABCMeta):
    """
    Base class for DSL expression builders.

    .. automethod:: __or__
    .. automethod:: __ror__
    .. automethod:: __xor__
    .. automethod:: __le__
    .. automethod:: __ge__
    .. automethod:: __rshift__
    .. automethod:: __invert__
    .. automethod:: __autoexpr__
    """
    __slots__ = ('reckless',)

    def __init__(self):
        self.reckless = False

    def __copy__(self):
        cls = self.__class__
        clone = cls.__new__(cls)
        clone.reckless = self.reckless
        return clone

    def invoke(self) -> 'Result':
        """
        Executes the command as currently configured and return a :class:`Result`
        instance to track its execution.
        """
        #TODO: launch the command
        return Result(self)

    def __autoexpr__(self) -> None:
        """
        Hook for the :mod:`transforms.autoexpr`
        """
        proc = self.invoke()
        proc.wait()

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

    def __int__(self):
        return self.to_status()

    def __bytes__(self):
        return self.to_binary()

    def __str__(self):
        return self.to_text()

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
        if isinstance(other, Pipeline):
            return NotImplemented

        #TODO: support callables
        if not isinstance(other, (IOBase, str, bytes, PurePath, Path)):
            return NotImplemented

        # print('{!r} __GT__ {!r}'.format(self, other))

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
        if not isinstance(rhs, Pipeline):
            return NotImplemented

        return Pipe(self, rhs)

    def __ror__(self, lhs) -> 'Pipe':
        """ Reverse for :meth:`__or__` to handle ``value | command``.
        """
        if not isinstance(lhs, Pipeline):
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

    def __invert__(self) -> 'Pipeline':
        """ ``~``
        """
        clone = self.__copy__()
        clone.reckless = not clone.reckless
        return clone

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


class Command(Pipeline):
    """
    .. automethod:: __lshift__
    .. automethod:: __rshift__
    """
    __slots__ = ('spec', 'args', 'no_raise',)

    def __init__(self, spec: 'BaseSpec') -> None:
        super().__init__()
        self.spec = spec
        self.args = []

        self.no_raise = [0]

    def __copy__(self) -> 'Command':
        clone = super().__copy__()
        clone.spec = self.spec
        clone.args = list(self.args)
        clone.no_raise = list(self.no_raise)
        return clone

    def __repr__(self):
        args = []
        for arg in self.args:
            if type(arg) == str:
                parsed = self.spec.parse_args(arg)
            elif type(arg) == tuple:
                parsed = self.spec.parse_args(*arg[0], **arg[1])
            else:
                args.append(repr(arg))
                continue

            args.extend(parsed)

        cmd = '{} {}'.format(self.spec.command, ' '.join(args))
        return '`{}`'.format(cmd.strip())

    def __getitem__(self, key) -> 'Command':
        """ Slice access records arguments almost in verbatim form, however
            there is splitting on whitespace so if you want to pass an argument
            containing whitespace it needs to be escaped with backslash.
        """
        if isinstance(key, slice):
            raise NotImplementedError()

        clone = self.__copy__()

        #TODO: detect paths/globs and create Path instances as args

        if type(key) != str:
            clone.args.append(key)
            return clone

        args = re.split(r'(?<!\\)\s', key)
        for arg in args:
            if arg == '' or arg.isspace():
                continue
            arg = re.sub(r'\\(\s)', r'\1', arg)  # unescape white space
            clone.args.append(arg)

        return clone

    def __call__(self, *args, **kwargs) -> 'Command':
        clone = self.__copy__()
        clone.args.append( (args, kwargs) )
        return clone

    def io(self, encoding=None, *, stdin=None, stdout=None, stderr=None):
        # encoding: applies to all
        # TODO: Shall it apply to commands only? or belongs to Pipeline?
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

        # TODO: Shall it apply to commands only? or belongs to Pipeline?

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




class Pipe(Pipeline):
    """
    Represents a pipe ``|`` operation.
    """
    def __init__(self, lhs: Pipeline, rhs: Pipeline) -> None:
        super().__init__()
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


class Redirect(Pipeline):
    """
    Represents a redirection ``>`` or ``>>`` operation.
    """
    def __init__(self, lhs: Pipeline, rhs: Path, *, appending=False) -> None:
        super().__init__()
        self.lhs = lhs
        self.rhs = rhs
        self.appending = appending

    def __repr__(self):
        op = '>>' if self.appending else '>'
        rhs = self.rhs.name if isinstance(self.rhs, IOBase) else repr(self.rhs)
        return '({!r} {} {})'.format(
            self.lhs, op, rhs)


class Application(Pipeline):
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
        super().__init__()
        self.lhs = lhs
        self.rhs = rhs

    def __repr__(self):
        return '({!r} << {!r})'.format(self.lhs, self.rhs)
