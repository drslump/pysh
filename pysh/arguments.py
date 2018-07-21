import os
from io import FileIO
from collections import defaultdict

from pysh.path import PathWrapper

from typing import cast, Any, Union, Optional, List, Dict, IO
TArgItem = Union[str, bool]
TArgValue = Union[None, TArgItem, List[TArgItem]]
TArgDict = Dict[str, TArgValue]




class Arguments:
    """
    Wraps an arguments dict to expose helper methods for common operations.

    Most operations have a *plural* version that returns an iterable of
    the values, regardless of it being originally multiple or not.

    It's also possible to provide a default value with the ``default``
    keyword. Take into account that his default value is not necesarily
    what should be returned if the option does not exists, it's the value
    that will be processed in that case.

    When ``raise_missing`` keyword is set to ``False`` then accessing a
    non-existent argument won't raise an error, returning ``None``.

    TODO: support --no-xxxxx arguments to unset flags.

    """
    #hack: used to detect when a default param is set
    DEFAULT: Any = {}

    HYPHEN = '/dev/stdin'  # default replacement for - in files

    @classmethod
    def from_argv(cls, argv: List[str]) -> 'Arguments':
        """ Simple system to parse arguments into a dictionary.

            - short options can be grouped ``-abc``
            - options have their value after ``=``
            - ``--`` stops interpreting options
            - anything else is an argument under ``_``
        """
        args = cast(Dict[str, List[TArgItem]], defaultdict(lambda: []))
        args['_'] = []

        parse_options = True
        for arg in argv:
            if parse_options:
                if arg == '--':
                    parse_options = False
                    continue

                parts = arg.split('=', 2)
                if arg.startswith('--'):
                    args[parts[0]].append(True if len(parts) < 2 else parts[1])
                    continue
                elif arg.startswith('-'):
                    for ch in parts[0][1:]:
                        args['-' + ch].append(True)

                    if len(parts) > 1:
                        args['-' + parts[0][-1]][-1] = parts[1]

                    continue

            args['_'].append(arg)

        #hack: mypy breaks if we construct with cls(...)
        return Arguments(dict(args), raise_missing=False)

    @classmethod
    def from_docopt(cls, args: TArgDict):
        """ Wraps the result of docopt parser.
        """
        #hack: mypy breaks if we construct with cls(...)
        return Arguments(args)

    def __init__(self, args: TArgDict, *, raise_missing=True) -> None:
        self._args = args
        self._raise_missing = raise_missing

    def one(self, name: str, *, default=DEFAULT) -> Optional[TArgItem]:
        """ Gets a single value for an argument.

            - Errors if the argument is unknown!
        """
        if name not in self._args:
            if self._raise_missing and default is self.DEFAULT:
                raise RuntimeError('Argument {} not found!'.format(name))
            else:
                return None if default is self.DEFAULT else default

        value = self._args[name]
        if value is None:
            return None
        elif isinstance(value, str):
            return value
        elif isinstance(value, list) and len(value):
            return value[0]
        else:
            return None

    def many(self, name: str, *, default=DEFAULT) -> List[TArgItem]:
        """ Get all values for an argument.

            - Errors if the argument is unknown!
        """
        if name not in self._args:
            if self._raise_missing and default is self.DEFAULT:
                raise RuntimeError('Argument {} not found!'.format(name))
            else:
                return [] if default is self.DEFAULT else default

        value = self._args[name]
        if value is None:
            return []
        elif isinstance(value, str):
            return [value]
        elif isinstance(value, list):
            return value

        assert False, 'expected arg value to be None, str or list'
        return None

    def get(self, name: str, default: Any = None) -> Any:
        """ Get the value associated to an argument or a default
        """
        return self.one(name, default=default)

    def gets(self, name: str, default: Any = DEFAULT) -> Any:
        """ Get the values associated to an argument or a default.

            - If the value is not a list it'll be wrapped in one.
            - If it's None an empty list is returned.
        """
        if default is self.DEFAULT:
            default = []

        return self.many(name, default=default)

    def __getitem__(self, name: str):
        if self._raise_missing:
            return self._args[name]
        else:
            return self._args.get(name)

    def __iter__(self):
        yield from self._args.items()

    def as_path(self, name: str, *, default=DEFAULT) -> Optional[PathWrapper]:
        """ Get argument as a Path
        """
        value = self.one(name, default=default)
        if value is None:
            return None

        if isinstance(value, bool):
            raise RuntimeError('Unable to create path from bool')

        return PathWrapper(value)

    def as_paths(self, name: str, *, default=DEFAULT) -> List[PathWrapper]:
        """ Get arguments as a Path
        """
        paths = []
        for v in self.many(name, default=default):
            if isinstance(v, bool):
                raise RuntimeError('Unable to create path from bool')
            paths.append(PathWrapper(v))

        return paths

    def _text(self, value: TArgItem, encoding: Optional[str], hyphen: Optional[str]) -> str:
        if isinstance(value, bool):
            raise RuntimeError('Unable to get text from bool')

        if hyphen and value == '-':
            value = hyphen

        with open(value, encoding=encoding) as fd:
            return fd.read()

    def as_text(self, name: str, *, encoding=None, hyphen=HYPHEN, default=DEFAULT) -> Optional[str]:
        """ Read the referenced file as text.

            - ``-`` will be interpreted as stdin, override with the ``hyphen`` keyword.
        """
        value = self.one(name, default=default)
        if value is None:
            return None

        return self._text(value, encoding, hyphen)

    def as_texts(self, name: str, *, encoding=None, hyphen=HYPHEN, default=DEFAULT) -> List[str]:
        """ Read the referenced files as text.

            - ``-`` will be interpreted as stdin, override with the ``hyphen`` keyword.
        """
        return [
            self._text(v, encoding, hyphen)
            for v in self.many(name, default=default)
            ]

    def _file(self, value: TArgItem, mode: Optional[str], writeable: bool, binary: bool, encoding: Optional[str], buffering: int, hyphen=HYPHEN) -> FileIO:
        if isinstance(value, bool):
            raise RuntimeError('Unable open file from bool')

        if not mode:
            mode = 'w' if writeable else 'r'
            if binary:
                mode += 'b'

        if hyphen and value == '-':
            value = hyphen

        file = open(value, mode=mode, encoding=encoding, buffering=buffering)
        return cast(FileIO, file)

    def as_file(self, name: str, *, mode=None, writeable=False, binary=False, encoding=None, buffering=-1, hyphen=HYPHEN, default=DEFAULT) -> Optional[FileIO]:
        """ Returns a file object or raises error if it can't be opened.

            - ``-`` will be interpreted as stdin, override with the ``hyphen`` keyword.
        """
        value = self.one(name, default=default)
        if value is None:
            return None

        return self._file(value, mode, writeable, binary, encoding, buffering, hyphen)

    def as_files(self, name: str, *, mode=None, writeable=False, binary=False, encoding=None, buffering=-1, hyphen=HYPHEN, default=DEFAULT) -> List[FileIO]:
        """ Returns file objects or raises error if it can't be opened.

            - ``-`` will be interpreted as stdin, override with the ``hyphen`` keyword.
        """
        return [
            self._file(v, mode, writeable, binary, encoding, buffering, hyphen)
            for v in self.many(name, default=default)
            ]

    def _str(self, value: TArgItem, at_load: bool) -> str:
        if isinstance(value, bool):
            raise RuntimeError('Unable to get str from bool')

        if value.startswith('@'):
            if os.path.exists(value[1:]):
                with open(value[1:]) as fd:
                    return fd.read()

        return value

    def as_str(self, name: str, *, atload=False, default=DEFAULT) -> Optional[str]:
        """ Get a string argument.

            - When ``atload`` is True and the argument starts with ``@`` then it
              checks for a matching file and if found it's read and returned.
        """
        value = self.one(name, default=default)
        if value is None:
            return None

        return self._str(name, atload)

    def as_strs(self, name: str, *, at=False, default=DEFAULT) -> List[str]:
        """ Get string arguments.

            - When ``atload`` is True and the argument starts with ``@`` then it
              checks for a matching file and if found it's read and returned.
        """
        return [
            self._str(v, at)
            for v in self.many(name, default=default)
            ]

    def _bool(self, value: TArgItem):
        if isinstance(value, bool):
            return value

        return value.lower() in ('1', 'yes', 'on', 'true', 't')

    def as_bool(self, name: str, *, default=DEFAULT) -> Optional[bool]:
        value = self.one(name, default=default)
        if value is None:
            return None

        return self._bool(value)

    def as_bools(self, name: str, *, default=DEFAULT) -> List[bool]:
        return [self._bool(v) for v in self.many(name, default=default)]

    def as_int(self, name: str, *, default=DEFAULT) -> Optional[int]:
        value = self.one(name, default=default)
        if value is None:
            return None

        return int(value)

    def as_ints(self, name: str, *, default=DEFAULT) -> List[int]:
        return [int(v) for v in self.many(name, default=default)]

    def as_float(self, name: str, *, default=DEFAULT) -> Optional[float]:
        value = self.one(name, default=default)
        if value is None:
            return None

        return float(value)

    def as_floats(self, name: str, *, default=DEFAULT) -> List[float]:
        return [float(v) for v in self.many(name, default=default)]

    def len(self, name) -> int:
        return len(self.many(name))
