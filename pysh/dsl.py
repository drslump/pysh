"""
Module for the types implementing the *domain specific language*. Normally
scripts won't need to construct these types directly but they are the
core of *pysh*.

"""

import os
import re
import pathlib
import glob
from abc import abstractmethod, ABCMeta
from collections import namedtuple
from io import IOBase

#TODO: Migrate to a custom implementation?
from braceexpand import braceexpand

from typing import Optional, Union, Iterator, List, Set, Pattern, Callable, Any, cast


def is_glob(value):
    """ Checks if a string contains unescaped glob characters
    """
    return any(
        len(m.group(1)) % 2 == 0
        for m in re.finditer(r'(\\*)[*?[]', value)
        )


def unescape(value):
    """ Removes escapes from a string
    """
    return re.sub(r'\\(.)', r'\1', value)


def unescape_glob(value):
    """ Keeps escapes of special glob characters using ranges.
    """
    value = re.sub(r'\\([*?[])', r'[\1]', value)
    return unescape(value)


def braceexpansion(value):
    """ The braceexpand module unescapes all the escapes, since it's the first
        step it'll undo any glob escaping. So before giving the value to the
        module we double any glob related escape.

        See: https://github.com/trendels/braceexpand/issues/2
    """
    value = re.sub(r'\\([*?[\\])', r'\\\\\1', value)
    return list(braceexpand(value))


#TODO: Can we inherit from .Path so it supports posix/windows flavours?
class Path(pathlib.PosixPath):
    """
    Represents a path.

    - ``/``: path segment(s) verbatim
    - ``//``: glob + brace-expansion segment(s)
    - ``//``: segment with anchored regex pattern or function
    - ``**``: same as // but recursive

    TODO: how to handle in command when a glob expansion produces 0 results?
        in Sh and Bash it just provides as argument the actual glob (i.e *.jpg),
        (unless globfail is set), but with support for regexes/funcs this is not
        an option. Csh/Fish raise an error which seems the sensible thing to do.

    TODO: Sort matches (joining digits so 4<11) ?? Use __lt__ and functools.total_ordering.
        To keep natural order, we can split the path into segments, next split segments
        into words/numbers/symbols, then use Python tuple comparison.
        pathlib does sort already splitting the segments, but it doesn't sort by
        natural order. I think the best approach is to not try to sort and refer to
        an external crate for natural sorting.
        http://natsort.readthedocs.io/en/master/howitworks.html#sorting-filesystem-paths

    """

    def __hash__(self):
        #TODO: Why is it not inherited?
        return super().__hash__()

    def __call__(self, *segments) -> 'Path':
        """
        Calling allows to join an arbitrary number of segments to a path. It's
        an alias to ``PurePath.joinpath``.
        """
        if not len(segments):
            raise TypeError('Expected at least one path segment')

        return self.joinpath(*segments)

    def joinpath(self, *args) -> 'Path':
        #TODO: Added because of pylint, check if joinpath returns a PurePath or respect the type
        return Path(super().joinpath(*args))


    def __getitem__(self, item: str) -> Union['Path', 'PathMatcher']:
        """
        Slicing has the following behaviour depending on the value:

         - contains brace expansions: returns a Matcher
         - contains glob characters: returns a Matcher
         - otherwise concats the value and returns a Path

        Escaping is supported with the backslash `\`, escaping non especial
        characters has no effect other than the backslash being removed.
        """
        #TODO: Support multiple items, error on slice instances
        items = braceexpansion(item)
        if len(items) > 1:
            items = [
                GlobMatcher(self, unescape_glob(x)) if is_glob(x)
                else self / unescape(x)
                for x in items]

            return ExpansionMatcher(items)

        item = items[0]
        if is_glob(item):
            return GlobMatcher(self, unescape_glob(item))

        return self / unescape(item)

    def _get_matcher_for(self, value: Union[str, Pattern, Callable]) -> 'PathMatcher':
        if type(value) == str:
            expansions = braceexpansion(value)
            if len(expansions) > 1:
                return ExpansionMatcher([
                    GlobMatcher(self, unescape_glob(x))
                    for x in expansions
                    ])
            else:
                return GlobMatcher(self, unescape_glob(expansions[0]))
        elif hasattr(value, 'fullmatch'):
            value = cast(Pattern, value)  #XXX help mypy
            return RegexMatcher(self, value)
        elif callable(value):
            return FilterMatcher(self, value)

        raise TypeError('Unsupported path matcher type {}'.format(type(value).__name__))

    def __floordiv__(self, rhs: Union[str, Pattern, Callable]) -> 'PathMatcher':
        """
        The ``//`` operator forces the use of a path matcher, if the value is a
        string it's handled as a glob with brace expansion, a regex pattern will
        keep a path if it matches the whole entry name and a callable receives
        Path instances keeping only those for which it returns True.
        """
        return self._get_matcher_for(rhs)

    def __pow__(self, rhs: Union[str, Pattern, Callable]) -> 'RecursiveMatcher':
        """
        Recursive globbing. See :meth:`__floordiv__` for more details.
        """
        # Prefer right-associativity to support the pathpow transform
        #TODO: Move this to a patch on pathpow when possible
        if hasattr(rhs, '__rpow__'):
            casted = cast(Any, rhs)  #XXX help mypy
            return casted.__rpow__(self)

        return RecursiveMatcher(self, self._get_matcher_for(rhs))

    def __eq__(self, other: object) -> bool:
        """
        Overload equality so we can support comparison against plain strings
        """
        #TODO: try to resolve before comparing equality?
        if isinstance(other, str):
            other = Path(other)

        return super().__eq__(other)

    def __bool__(self):
        """
        Checks if the path exists.
        """
        return self.exists()

    ## Helpers accept an optional subpath unlike pahtlib

    def exists(self, subpath=None):
        """
        Tests if a path exists.
        """
        if subpath:
            return (self/subpath).exists()
        else:
            return super().exists()

    #TODO: support for the other helpers in pathlib

    def is_empty(self, subpath=None):
        """
        Check if a path refers to an empty file.
        Will raise an OSError if there is some issue accessing the file.
        """
        p = self/subpath if subpath else self
        return p.stat().st_size() == 0


class PathMatcher:
    """
    Base class for path matcher types.
    """

    def iter_posix(self) -> Iterator[str]:
        """
        Matchers work with posix like path strings to avoid creating Path
        objects if not needed. The iterator interface feeds from this one
        to yield Path objects.
        """
        raise NotImplementedError('Descendant types should implement it')

    def for_path(self, path: pathlib.PurePath) -> 'PathMatcher':
        raise NotImplementedError('Descendant types should implement it')

    def __iter__(self) -> Iterator[Path]:
        for p in self.iter_posix():
            yield Path(p)

    def __int__(self):
        """
        Get the number of matches, to do so **it has to perform the matching**
        so if you intend to use the results afterwards it's best to cast to
        list() first.
        """
        cnt = 0
        for _ in self.iter_posix():
            cnt += 1
        return cnt

    # Optimize for some comparisons

    def __bool__(self):
        return self.__gt__(0)

    def __eq__(self, other):
        if type(other) != int:
            return NotImplemented

        cnt = 0
        for _ in self.iter_posix():
            if cnt == other:
                return True
            cnt += 1
        return False

    def __lt__(self, other):
        if type(other) != int:
            return NotImplemented

        cnt = 0
        for _ in self.iter_posix():
            if cnt >= other:
                return False
            cnt += 1
        return True

    def __gt__(self, other):
        if type(other) != int:
            return NotImplemented

        cnt = 0
        for _ in self.iter_posix():
            if cnt > other:
                return True
            cnt += 1
        return False

    def __le__(self, other):
        if type(other) != int:
            return NotImplemented

        return self.__lt__(other+1)

    def __ge__(self, other):
        if type(other) != int:
            return NotImplemented

        return self.__gt__(other-1)


class GlobMatcher(PathMatcher):
    """
    Matcher based on glob expressions.
    """
    __slots__ = ('path', 'pattern',)

    def __init__(self, path: pathlib.PurePath, pattern: str) -> None:
        self.path = path
        self.pattern = pattern

    def for_path(self, path: pathlib.PurePath) -> 'GlobMatcher':
        return GlobMatcher(path, self.pattern)

    def iter_posix(self) -> Iterator[str]:
        """
        Use the glob module instead of pathlib.

        TODO: On Windows we might have to handle casefolding.
        """
        path = os.path.join(self.path, self.pattern)
        yield from glob.iglob(path)


class RegexMatcher(PathMatcher):
    """
    Matcher based on regex patterns.
    """
    __slots__ = ('path', 'pattern')

    def __init__(self, path: pathlib.PurePath, pattern: Pattern) -> None:
        self.path = path
        self.pattern = pattern

    def for_path(self, path: pathlib.PurePath) -> 'RegexMatcher':
        return RegexMatcher(path, self.pattern)

    def iter_posix(self) -> Iterator[str]:
        match = self.pattern.fullmatch
        path = self.path.as_posix()
        with os.scandir(path) as it:
            for entry in it:
                if match(entry.name):
                    yield entry.path


class FilterMatcher(PathMatcher):
    """
    Matcher based on filtering functions.
    """
    __slots__ = ('path', 'func')

    def __init__(self, path: pathlib.PurePath, func: Callable) -> None:
        self.path = path
        self.func = func

    def for_path(self, path: pathlib.PurePath) -> 'FilterMatcher':
        return FilterMatcher(path, self.func)

    def iter_posix(self) -> Iterator[str]:
        func = self.func
        path = self.path.as_posix()
        for p in Path(self.path).iterdir():
            if func(p):
                # try to have the same format as other matchers
                yield os.path.join(path, p.name)


#TODO: Seems super slow even with simple globs!
class RecursiveMatcher(PathMatcher):
    """
    Recursive matcher that will apply a child matcher against a path tree.
    """
    __slots__ = ('path', 'matcher')

    def __init__(self, path: pathlib.PurePath, matcher: PathMatcher) -> None:
        self.path = path
        self.matcher = matcher

    def for_path(self, path: pathlib.PurePath) -> 'RecursiveMatcher':
        return RecursiveMatcher(path, self.matcher)

    def iter_posix(self) -> Iterator[str]:
        matcher = self.matcher

        # TODO: use itertools to keep it dry
        m = matcher.for_path(self.path)
        for pp in m.iter_posix():
            yield pp

        for p in Path(self.path).rglob('*'):
            if p.is_dir():
                m = matcher.for_path(p)
                for pp in m.iter_posix():
                    yield pp


class ExpansionMatcher(PathMatcher):
    """
    Holds the results of brace expansion which can be concrete paths or child
    matchers.
    """
    __slots__ = ('expansions',)

    def __init__(self, expansions: List[Union[Path, PathMatcher]]) -> None:
        self.expansions = expansions

    def for_path(self, path: pathlib.PurePath) -> 'ExpansionMatcher':
        raise TypeError('ExpansionMatcher does not support for_path')

    def iter_posix(self) -> Iterator[str]:
        seen: Set[str] = set()
        for expansion in self.expansions:
            if not isinstance(expansion, PathMatcher):
                path = str(expansion)
                if path not in seen:
                    seen.add(path)
                    yield path
                continue

            for p in expansion.iter_posix():
                if p not in seen:
                    seen.add(p)
                    yield p


# Internal type to hold arguments when constructing commands
Arg = namedtuple('Arg', ('positional', 'keywords'))




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
    def parse_args(self, positional, keyword) -> List[Any]:
        """
        Used by :meth:`CommandBuilder` call and slicing protocols to convert
        their received values into arguments according to the spec.

        .. TODO:: Does it belong in the interface? shouldn't it be part of External?
        """

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

    def __copy__(self):
        cls = self.__class__
        clone = cls.__new__(cls)
        return clone

    def invoke(self) -> 'Result':
        """
        Executes the command as currently configured and return a :class:`Result`
        instance to track its execution.

        The actual implementation is on the derived classes.
        """
        raise NotImplementedError()

    def pipe(self, stdout=None, *, stderr=None) -> Union['Pipe', 'Piperr']:
        """ Explicit interface for the ``|`` and ``^`` operators.
        """
        result = self.__copy__()
        if stderr is not None:
            result = result ^ stderr
        if stdout is not None:
            result = result | stdout

        return result

    def __autoexpr__(self) -> None:
        """
        Hook for the :mod:`transforms.autoexpr`
        """
        proc = self.invoke()
        proc.wait()

    def __int__(self):
        """
        Invoke and get the exit status code.
        """
        proc = self.invoke()
        proc.wait()
        return proc.status

    def __bytes__(self):
        """
        Invoke and get the stdout as binary.
        """
        proc = self.invoke()
        proc.wait()
        return proc.stdout.read()

    def __str__(self):
        """
        Invoke and get the stdout as text.
        """
        #TODO: This needs further work to handle the encoding properly
        return bytes(self).decode('utf-8')

    def __gt__(self, other) -> 'Redirect':
        """ :ref:`Redirection: >`
        """
        if isinstance(other, Pipeline):
            #TODO: issue warning log
            return NotImplemented

        #TODO: support callables
        if isinstance(other, str):
            return Redirect(self, pathlib.PurePath(other))
        elif isinstance(other, (pathlib.PurePath, IOBase)):
            return Redirect(self, other)
        else:
            return NotImplemented

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

        if isinstance(rhs, str):
            rhs = pathlib.PurePath(rhs)

        return Piperr(self, rhs)

    def __invert__(self) -> 'Reckless':
        """ ``~``
        """
        return Reckless(self)


class Command(Pipeline):
    """
    .. automethod:: __lshift__
    .. automethod:: __rshift__
    """
    __slots__ = ('_spec', '_args', '_no_raise',)

    def __init__(self, spec: BaseSpec) -> None:
        super().__init__()
        self._spec = spec
        self._args: List[Arg] = []
        self._no_raise: List[int] = [0]

    def __copy__(self) -> 'Command':
        clone = super().__copy__()
        clone._spec = self._spec
        clone._args = list(self._args)
        clone._no_raise = list(self._no_raise)
        return clone

    def __repr__(self):
        args = []
        for arg in self._args:
            args.extend('{!r}'.format(v) for v in arg.positional)
            args.extend('{}={!r}'.format(k,v) for k,v in arg.keyword.items())

        cmd = '{} {}'.format(self._spec.command, ' '.join(args))
        return '`{}`'.format(cmd.strip())

    def __getitem__(self, key) -> 'Command':
        """
        Slice access records arguments almost in verbatim form, however there
        is splitting on whitespace so if you want to pass an argument containing
        whitespace it needs to be escaped with backslash.
        """
        #TODO: support multiple values cmd[1,2,3]

        if isinstance(key, slice):
            raise NotImplementedError()

        clone: Command = self.__copy__()

        #TODO: detect paths/globs and create Path instances as args

        if type(key) != str:
            clone._args.append(Arg((key,), {}))
            return clone

        args = re.split(r'(?<!\\)\s', key)
        for arg in args:
            if arg == '' or arg.isspace():
                continue
            arg = re.sub(r'\\(\s)', r'\1', arg)  # unescape white space
            clone._args.append(Arg((arg,), {}))

        return clone

    def __getattr__(self, name: str) -> 'Command':
        """
        Accessing an attribute sets a boolean option:

        >>> jq.compact
          # jq --compact
        >>> tar.x.v.z.f('archive.tgz')['*.py']
          # tar -xvzf archive.tgz *.py
        """
        if name.startswith('_'):
            raise AttributeError

        return self(**{name: True})

    def __call__(self, *args, **kwargs) -> 'Command':
        clone = self.__copy__()
        clone._args.append(Arg(args, kwargs))
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
            clone._no_raise = list(range(256))
        else:
            clone._no_raise = list(statuses)
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
    def __init__(self, lhs: Pipeline, rhs: Union[pathlib.PurePath, IOBase], *, appending=False) -> None:
        super().__init__()
        self.lhs = lhs
        self.rhs = rhs
        self.appending = appending

    def __repr__(self):
        op = '>>' if self.appending else '>'
        rhs = self.rhs.name if isinstance(self.rhs, IOBase) else repr(self.rhs)
        return '({!r} {} {})'.format(self.lhs, op, rhs)


class Reckless(Pipeline):
    """
    Represents the reckless operator ``~``
    """
    __slots__ = ('expr',)

    def __init__(self, expr: Pipeline) -> None:
        self.expr = expr

    def __repr__(self) -> str:
        return '~{!r}'.format(self.expr)


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


class Result:
    __slots__ = ('pipeline', 'status', 'stdin', 'stdout', 'stderr')

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
