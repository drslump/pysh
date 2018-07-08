try:
    from pathlib2 import PurePath, PosixPath
except ImportError:
    from pathlib import PurePath, PosixPath


class PathWrapper(PosixPath):

    def __floordiv__(self, rhs):
        #TODO: can we make this lazy so it can be in the middle of a path?
        return self.glob(rhs)

    def __rfloordiv__(self, lhs):
        return Path(lhs).glob(self)

    def __eq__(self, other):
        """ Overload equality so we can support comparison against plain strings
        """
        #TODO: try to resolve before comparing equality?
        if not isinstance(other, PathWrapper):
            other = PathWrapper(other)

        return super(PathWrapper, self).__eq__(other)

    def __getitem__(self, spec):
        if spec in ('.', '/', '~'):
            return PathWrapper(spec)

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

    def __call__(self, path):
        """ use: p('path/to/file')
        """
        return PathWrapper(path)
