"""
.. TODO::
    Paths globbing should be lazy too. This means that we need to use
    pathlib internally and expose a custom interface that resolves on str and
    iter. That would allow to do this:

    >>> imgs = _ // '*.jpg' + '*.gif' + '*.png'
    >>> if len(imgs) > 5:  # globbing is computed
    >>>   zip(imgs)      # globbing is computed again

Internally a PathWrapper is always a collection with 0 or more elements.
The rules are:

    >>> str(*.py)  ->  'foo.py bar.py'  # space separated
    >>> int(path) -> len(path) -> number of matching files  # globs can yield 0
    >>> list(path) -> get a snapshot of the current paths
    >>> bool(gpath) -> gpath.exists()  -> at least one match

    >>> glob1 + glob2 -> adds glob2 to glob1
    >>> glob1 - glob2 -> substracts glob2 from glob1
    >>> _ ** 'tmp-?.py' -> recursive glob -> _ // '**/tmp-?.py'

One problem of handling paths as collections is that we lose some of the
functionality of pathlib (i.e `.is_file`). Even if the collection yields
Path objects, the ergonomics do not seem to be great:

    >>> p = _ / 'foo.txt'
    >>> p.is_file()  # error
    >>> p[0].is_file()   # works

One solution would be to proxy those methods to the whole collection like:

    >>> p.is_file()  -> all(x.is_file for x in p)

But it can perhaps be very confusing if the path matches different items,
for instance if there is a directory on it. Although for normal use this
probably makes sense. However things like `.rename` or `.open` wouldn't
work.

A least surprising option may be to internally control if the path is
concrete or a glob, if it's a glob those proxied options would raise an
error. __len__ for a non glob would return the path length, on glob the
number of matches.

>>> _['*.jpg']  # slice supports globing
"""


from pathlib import PurePath, PosixPath, Path

from typing import Union, Iterator, Iterable, cast
TPathLike = Union[str, PurePath]


class PathWrapper(PosixPath):

    def __floordiv__(self, rhs: str) -> Iterable[Path]:
        """ regexp is anchored to the start. This avoids expensive traversals
            for simple use cases. User can always start with `*` (we convert to .*)
            if anchored is not ok for the use case.

            - starts with `*` -> [^/]*?  (no recursive)
            - starts with `**` -> .*?  (recursive)
        """
        raise NotImplementedError()

    def __rfloordiv__(self, lhs: str) -> Iterable[Path]:
        raise NotImplementedError()

    def __eq__(self, other: object) -> bool:
        """ Overload equality so we can support comparison against plain strings
        """
        #TODO: try to resolve before comparing equality?
        if not isinstance(other, PathWrapper):
            other = PathWrapper(cast(TPathLike, other))

        return super().__eq__(other)

    def __getitem__(self, spec: Union[int, slice, str]) -> Path:
        if spec in ('.', '/', '~'):
            return PathWrapper(str(spec))

        #TODO: check slice

        # if spec in ('.', '/', '~', r'\\'):
        #     return Path(spec=spec)
        # elif spec == r'\':
        #     return Path(spec='/')
        # elif spec == '//':
        #     return Path(spec=r'\\')
        # elif spec.is_letter():
        #     return Path(spec=spec.lower())
        # elif all(ch == '.' for ch in spec):
        #     return Path(spec=spec)
        # else:

        raise RuntimeError('Unsupported path spec {0}'.format(spec))

    def __call__(self, path: TPathLike) -> Path:
        """ use: _('path/to/file')
        """
        return PathWrapper(path)

    def as_path(self, *, glob=False) -> Union[Path, Iterator[Path]]:
        """ Returns a path object if no globbing is setup. If glob is set
            it returns an Iterator of path objects, otherwise raises ValueError.

            It'll return a Path/Posix/Windows path object according to the
            current configuration.
        """
