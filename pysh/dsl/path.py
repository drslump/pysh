"""

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


import os
import re
import pathlib
import glob

from braceexpand import braceexpand

from typing import Union, Iterator, List, Pattern, Callable, Any, cast


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

    def __getitem__(self, item: str) -> Union['Path', 'PathMatcher']:
        """
        Slicing has the following behaviour:

         - contains brace expansions: returns a Matcher
         - contains glob characters: returns a Matcher
         - otherwise concats the value and returns a Path

        Escaping is supported with the backslash `\`, escaping non especial
        characters has no effect other than the backslash being removed.
        """
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
            return rhs.__rpow__(self)

        return RecursiveMatcher(self, self._get_matcher_for(rhs))

    def __eq__(self, other: object) -> bool:
        """
        Overload equality so we can support comparison against plain strings
        """
        #TODO: try to resolve before comparing equality?
        if not isinstance(other, Path):
            other = Path(other)

        return super().__eq__(other)

    def __bool__(self):
        """
        Checks if the path exists.
        """
        return self.exists()


class PathMatcher:
    """
    Base class for matcher types.
    """

    __slots__ = ('path', 'pattern',)

    def __init__(self, path: Path, pattern: str = None):
        self.path = path
        self.pattern = pattern

    def iter_posix(self) -> Iterator[str]:
        """
        Matchers work with posix like path strings to avoid creating Path
        objects if not needed. The iterator interface feeds from this one
        to yield Path objects.
        """
        raise NotImplemented()

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
        for x in self.iter_posix():
            cnt += 1
        return cnt

    # Optimize for some comparisons

    def __bool__(self):
        return self.__gt__(0)

    def __eq__(self, other):
        if type(other) != int:
            return NotImplemented

        cnt = 0
        for p in self.iter_posix():
            if cnt == other:
                return True
            cnt += 1
        return False

    def __lt__(self, other):
        if type(other) != int:
            return NotImplemented

        cnt = 0
        for p in self.iter_posix():
            if cnt >= other:
                return False
            cnt += 1
        return True

    def __gt__(self, other):
        if type(other) != int:
            return NotImplemented

        cnt = 0
        for p in self.iter_posix():
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

    def iter_posix(self) -> Iterator[str]:
        """
        Use the glob module instead of pathlib.

        TODO: On Windows we might have to handle casefolding.
        """
        path = os.path.join(self.path, self.pattern)
        yield from glob.iglob(path)


class RegexMatcher(PathMatcher):
    __slots__ = ('path', 'pattern')

    def __init__(self, path: Path, pattern: Pattern):
        self.path = path
        self.pattern = pattern

    def iter_posix(self) -> Iterator[str]:
        match = self.pattern.fullmatch
        path = self.path.as_posix()
        with os.scandir(path) as it:
            for entry in it:
                if match(entry.name):
                    yield entry.path


class FilterMatcher(PathMatcher):
    __slots__ = ('path', 'func')

    def __init__(self, path: Path, func: Callable):
        self.path = path
        self.func = func

    def iter_posix(self) -> Iterator[str]:
        func = self.func
        path = self.path.as_posix()
        for p in self.path.iterdir():
            if func(p):
                # try to have the same format as other matchers
                yield os.path.join(path, p.name)


#TODO: Seems super slow even with simple globs!
class RecursiveMatcher(PathMatcher):
    __slots__ = ('path', 'matcher')

    def __init__(self, path: Path, matcher: PathMatcher):
        self.path = path
        self.matcher = matcher

    def iter_posix(self) -> Iterator[str]:
        matcher = self.matcher
        saved = matcher.path  #TODO: fix this hack (not thread safe!)
        try:
            # TODO: use itertools to keep it dry
            matcher.path = self.path
            for pp in matcher.iter_posix():
                yield pp

            for p in self.path.rglob('*'):
                if p.is_dir():
                    matcher.path = p
                    for pp in matcher.iter_posix():
                        yield pp
        finally:
            matcher.path = saved


class ExpansionMatcher(PathMatcher):
    """
    Holds the results of brace expansion.
    """
    __slots__ = ('expansions',)

    def __init__(self, expansions: List[Union[Path, PathMatcher]]):
        self.expansions = expansions

    def iter_posix(self) -> Iterator[str]:
        seen = set()
        for expansion in self.expansions:
            if not isinstance(expansion, PathMatcher):
                if expansion not in seen:
                    seen.add(p)
                    yield expansion
                continue

            for p in expansion.iter_posix():
                if p not in seen:
                    seen.add(p)
                    yield p

