"""
.. TODO::
    Paths globbing should be lazy too. This means that we need to use
    pathlib internally and expose a custom interface that resolves on str and
    iter. That would allow to do this:

    >>> imgs = _ // '*.jpg'
    >>> if len(imgs) > 5:  # globbing is computed
    >>>   zip(imgs)        # globbing is computed again


>>> _['*.jpg']  # slice supports globbing


TODO: Implement brace expansion? https://pypi.org/project/braceexpand/
      Note though that in sh it's not part of globbing, it just executes
      first and can generate multiple variants of a glob.


globbing applies only to a path segment, be it a shell style glob or a
regex. For shell style though there is automatic segment extraction, so
``foo-*/*.jpg`` is converted to ``foo-*`` * ``*.jpg``. In the case of
regex this is not possible so only a single segment is allowed. This
solves one of the main issues with using regexes that was having to
traverse the whole directory structure to match, now it just applies to
the current level.

    _* '*.jpg'
    _** '{foo,bar}-*.jpg'
    _// r'\.jpg$'

also functions can be given to ``//``, which also operate on a single level:

    _// lambda path: path.isFile()

returning True means that the match should be kept. They are left associative,
so:

    _// Path.isFile / '.*' // lambda p: p.name.startswith('foo')

Problem is that there is no clean way to apply a regex recursively, so perhaps
regexes should always traverse? and try to optimize by look for ``^`` in it.

    _ // '\.jpg$'  # traverses
    _ // '^(foo|bar|baz).*\.jpg$   # anchored to a single level
    _ // '(foo|bar|baz)/.*\.jpg$   # detect directories? won't work :(

A mitigation might be to allow regex to expand multiple segments but use
.match semantics, so it's always anchored and requires the user to opt out
by using ``.*`` at the start. WARNING: even if we start anchored, the common
``.*`` will traverse directories, unless we modify the regex so the `.`
doesn't match ``/`` it's very dangerous and it's best to keep it at the
segment level. For traversal we can always do:

    paths = _ // '**'
    matching = [ x for x in paths if rex.search(str(x)) ]


TODO: Having * for globbing is a bit ugly, ideally we should have 4 ops:

    - ``/``: path segment
    - ``//``: glob or filter-function
    - ``**``: recursive glob or filter-function
    - ``^``: anchored regex glob

    Will binding precedence be an issue here?

    _ / 'foo' // '*.jpg'
    ( _ / 'foo' ) // '*.jpg'

    _ / 'foo' ** '*.jpg'
    (_ / ('foo' ** '*.jpg'))  # WRONG!!!!!

    _ / 'foo' ^ '.*\.jpg$'
    (_ / 'foo') ^ '.*\.jpg$'

    _ / 'foo' ^ '(foo|bar).*' / 'baz'
    (_ / 'foo') ^ ('(foo|bar)' / 'baz')  # WRONG!

    So ** is out, unless we can solve it easily and without caveats in precedence
    transform, for recursive we can always do:

        _ // '**/*.jpg'
        _ // '**' // filter_fn   # better, because it can be very expensive! :)
        _ // '**' ^ '(foo|bar).*\.jpg' /

    The ``^`` case is more complicated because we can't mess with it in precedence
    or we would break piperr surely. We could use a different symbol for regex,
    for instance ``@``:

        _ / 'foo' @ '(foo|bar).*' / 'bar.txt'

    Or just don't have an operator for regex, we can always provide a pattern and
    do as with filter functions:

        _ / 'foo' / _.re('(foo|bar).*') / 'bar.txt'

    And we can make more ergonomic by having a transform for "regex strings",
    which is probably useful for other use cases:

        re'(foo|bar).*'  ->  re.compile(r'(foo|bar)', re.X)

        _'foo' // re'(foo|bar).*' / 'bar.txt'

    So to sumarize:

        ``/``: path segment(s) verbatim
        ``//``: glob + brace-expansion segment(s)
        ``//``: segment with anchored regex pattern or function
        ``**``: same as // but recursive (ONLY if possible with transform)


TODO: how to handle in command when a glob expansion produces 0 results?
      in Sh and Bash it just provides as argument the actual glob (i.e *.jpg),
      (unless globfail is set), but with support for regexes/funcs this is not
      an option. Csh/Fish raise an error.

TODO: Sort matches (joining digits so 4<11) ??


"""


import os
import pathlib

from typing import Union, Iterator, Iterable, Generator, Any, cast


#TODO: Can we inherit from .Path so it supports posix/windows flavours?
class Path(pathlib.PosixPath):

    def __call__(self, *segments) -> 'Path':
        if not len(segments):
            raise TypeError('Expected at least one segment')

        for segment in segments:
            return self / segment

    def __getitem__(self, item) -> Union['Path', 'GlobPath']:
        """ Supports globbing!
        """
        # TODO: check for globbing syntax
        return self / item

    def __mul__(self, rhs: str) -> 'Glob':
        """ Globbing
        """
        return Glob(self, rhs)

    def __pow__(self, rhs: str) -> 'Glob':
        """ Recursive globbing
        """
        # Prefer right-associativity to support the pathpow transform
        if hasattr(rhs, '__rpow__'):
            return rhs.__rpow__(self)

        return GlobRecursive(self, rhs)

    def __truediv__(self, rhs: str) -> 'Path':
        if isinstance(rhs, Glob):
            return rhs

        return super().__truediv__(rhs)

    def __floordiv__(self, rhs: str) -> 'Glob':
        return GlobRegex(self, rhs)

    def __eq__(self, other: object) -> bool:
        """ Overload equality so we can support comparison against plain strings
        """
        #TODO: try to resolve before comparing equality?
        if not isinstance(other, Path):
            other = Path(other)

        return super().__eq__(other)

    def __bool__(self):
        """ Checks if the path exists
        """
        return self.exists()


class Segment:
    """ Helper to wrap a value to signal it's part of a path
    """
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'Segment({!r})'.format(self.value)

    def __rpow__(self, lhs):
        return GlobRecursive(lhs, self.value)



class Glob:

    __slots__ = ('path', 'pattern',)

    def __init__(self, path: Union[Path,'Glob'], pattern: str =None):
        self.path = path
        self.pattern = pattern

    def __copy__(self) -> 'Glob':
        clone = self.__new__()
        clone.path = self.path
        clone.pattern = self.pattern
        return clone

    def map(self, fn) -> Generator[Path, None, None]:
        return map(fn, self)

    def filter(self, fn) -> Generator[Path, None, None]:
        return filter(fn, self)

    def reduce(self, fn, initial=None) -> Any:
        return reduce(fn, self, initial)

    def __iter__(self) -> Iterator[Path]:
        yield from self.as_paths()

    def __len__(self):
        return len(list(self))

    def __bool__(self):
        # Optimized to shorcut on the first pattern found
        for p in self:
            return True
        else:
            return False


class GlobRecursive(Glob):
    pass


class GlobRegex(Glob):
    pass
