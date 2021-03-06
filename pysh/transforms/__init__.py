"""
This package holds official code transformation modules.

A transformation module defines at least one of:

  - ``lexer(code: TextIOBase, fname: str) -> TextIOBase``
  - ``parser(root: AST, fname: str) -> AST``
  - ``patch(types: Dict[str, type]) -> None``

Additionally the module symbols referenced on its ``__all__`` will
be made available as globals for the script. This allows to define
*runtime* functions on the generated code.

Transform modules might want to patch the DSL types in order to provide
additionaly features or modify somehow the standard behaviour. Before
compiling some script code the transform will have a chance for doing
so via the ``patch`` hook. It's very important that module transforms
don't try to monkey patch the types by importing them, instead it should
use the types provided to the ``patch`` function.

TODO: Implement patching support for the DSL:

    - Create a lazy-dict with the types in the DSL
    - When a type is required it returns a new subtype
    - Pass the dict to the patch function
    - Get as result a dict with the types to override
    - add a global __PYSH_DSL_OVERRIDES__ with that override
    - DSL types implement a __new__ that looks into
      __PYSH_DSL_OVERRIDES__, if found return an instance of that
      type, otherwise act as normal.
    - compiled scripts should get the modified type, a
      descendant of the standard one. Other scripts will
      not be affected, unless the user interacts with the
      DSL directly in some of its code that gets imported
      as a module.


.. note:: The code AST is wrapped in a ``FunctionDef`` before calling
          a transformer parser. Transforms should expect a top level
          function wrapping the script code.
"""

import builtins
import ast
import logging
import re
import tokenize
from collections import ChainMap
from io import IOBase, TextIOBase, StringIO
from importlib import import_module
from types import FunctionType, CodeType

import pysh

from typing import Union, Callable, Dict, List, Tuple, Iterator, Optional, Any, TypeVar


STARTMARKER = tokenize.TokenInfo(type=-1, string='', start=(0,0), end=(0,0), line='')


logger = logging.getLogger(__name__)


T = TypeVar('T')
def zip_prev(generator: Iterator[T], initial: T = None) -> Iterator[Tuple[Optional[T],T]]:
    """ Helper wrapper for tokens generators that will provide a tuple with
        the previous item and the current one. The initial previous item can
        be provided.

        >>> for ptkn, ctkn in zip_prev(tokens, None):
        >>>   if ptkn == '.' and ctkn == 'method':
        >>>      ...
    """
    prev = initial
    for item in generator:
        yield prev, item
        prev = item


class TokenIO(StringIO):
    """
    Helper class for lexers that understands Python tokenize's TokenInfo
    and can generate an output string that respects the original white space.

    It also wraps ``tokenize.tokenize`` so tokens, instead of lines, will be
    obtained when iterating.
    """
    def __init__(self, code: Union[str, StringIO] = None) -> None:
        if isinstance(code, StringIO):
            code_str = code.getvalue()
        elif code:
            code_str = code
        else:
            code_str = ''

        super().__init__(code_str)

        self.line = 1
        self.column = 0

    def iter_tokens(self) -> Iterator[tokenize.TokenInfo]:
        #XXX .generate_tokens is deprecated but .tokenize requires a bytes stream
        yield from tokenize.generate_tokens(self.readline)

    def write(self, value: str):
        lines = value.count('\n')
        if lines > 0:
            self.line += lines
            self.column += len(value) - value.rfind('\n')
        else:
            self.column += len(value)

        return super().write(value)

    def write_token(self, token: tokenize.TokenInfo, *, override: str = None):
        """ Write a token adjusting white space, optionally overriding its
            output with a custom value.
        """
        if token.type in (tokenize.ENDMARKER, STARTMARKER):
            return

        line, column = token.start
        if line - self.line > 0:
            super().write('\n' * (line-self.line))
            self.column = 0

        if column - self.column > 0:
            super().write(' ' * (column-self.column))

        self.line, self.column = token.end
        if token.type in (tokenize.NEWLINE, tokenize.NL):
            # NL actually reports the current line so let's adjust manually
            self.line += 1
            self.column = 0

        if override is None:
            override = token.string

        return super().write(override)


def _get_transform_name(transform: Callable):
    import inspect  # lazy import
    return '{}.{}'.format(inspect.getmodule(transform).__name__, transform.__name__)


def _apply_transform(transform: Callable, obj: Any, fname: str) -> Any:
    try:
        try:
            return transform(obj, fname=fname)
        except TypeError:
            logger.debug(
                'Transform %s does not support the `fname` keyword',
                _get_transform_name(transform))

            return transform(obj)
    except Exception as ex:
        raise RuntimeError(
            'Failed running {} transform: {}'.format(
                _get_transform_name(transform), ex
            ))


class Compiler:
    """ Allows to register transform modules and obtain an executable
        function from some source code.
    """

    FALLBACK_PREFIXES = [
        'pysh_transform_',      # third party
        'pysh.transforms.',     # internal
    ]

    def __init__(self, transforms: List[str] = []) -> None:
        self.lexers: List[Callable] = []
        self.parsers: List[Callable] = []
        self.symbols: Dict[str, Any] = {}
        self.patchers: List[Callable] = []

        for transform in transforms:
            self.add_transform(transform)

    def add_transform(self, transform: str):
        """
        Accepts a module name which can be inside a package.

        If it fails to find the module it will try with a list of common
        prefixes from :const:`FALLBACK_PREFIXES`, this allows to
        package a transform module for distribution.

        .. Hint:: to load an arbitrary python file just set the PYTHONPATH to
                  point to its directory before running the command.
        """
        module = None

        # testing: allow to pass a module instance directly
        if not isinstance(transform, str):
            module = transform
            transform = getattr(module, '__name__')
        else:
            for prefix in [''] + self.FALLBACK_PREFIXES:
                try:
                    module = import_module(prefix + transform)
                    transform = prefix + transform
                    logger.info('Loaded transform module %s', transform)
                    break
                except ModuleNotFoundError as ex:
                    logger.debug(
                        'Tried importing transform %s but not found', prefix + transform)
                except ImportError as ex:
                    raise RuntimeError(
                        'Error importing transform {}'.format(prefix + transform)) from ex

            if not module:
                raise RuntimeError('Unable to find transform {}'.format(transform))

        assert module, 'expected a valid module'
        #TODO: Warn if no lexer or parser was found

        if hasattr(module, 'lexer'):
            logger.debug('Registering lexer from %s', transform)
            self.lexers.append(getattr(module, 'lexer'))

        if hasattr(module, 'parser'):
            logger.debug('Registering parser from %s', transform)
            self.parsers.append(getattr(module, 'parser'))

        if hasattr(module, 'patch'):
            logger.debug('Registering patch from %s', transform)
            self.patchers.append(getattr(module, 'patch'))

        if hasattr(module, '__all__'):
            for symbol in getattr(module, '__all__'):
                logger.debug('Registering symbol %s from %s', symbol, transform)
                self.symbols[symbol] = getattr(module, symbol)

    def lex(self, code: TextIOBase, fname='<string>') -> TextIOBase:
        for lexer in self.lexers:
            code = _apply_transform(lexer, code, fname=fname)
            code.seek(0)  # make sure its cursor is reset

        return code

    def parse(self, code: TextIOBase, fname='<string>', name='_pysh_func') -> ast.AST:
        # Get an AST from the input code
        node = ast.parse(code.read())  #type: ignore

        # Now wrap the script in a function so we can get a reference to it.
        wrapper = ast.parse('def {}(): pass'.format(name))
        wrapper.body[0].body = node.body  #type: ignore

        for parser in self.parsers:
            wrapper = _apply_transform(parser, wrapper, fname=fname)

        # Ensure locations are ok before compiling
        ast.fix_missing_locations(wrapper)

        return wrapper

    def compile(self, code: TextIOBase, fname='<string>') -> Callable[[], Any]:
        """
        Given some script code it'll perform any configured transformation
        and return a function containing the compiled code. That function can
        be called to execute the script.
        """
        #TODO: a way to offset the positions when used as decorator
        #SEE: http://code.activestate.com/recipes/578353-code-to-source-and-back/

        name = 'pysh_{}'.format(re.sub(r'\W', '_', fname))

        code = self.lex(code, fname)
        node = self.parse(code, fname, name)
        comp = compile(node, fname, 'exec')

        # Execute to trigger the creation of the wrapping function as a global
        #TODO: what pysh globals to include?
        glbls = dict(ChainMap(self.symbols,  pysh.__dict__, builtins.__dict__))
        exec(comp, glbls)

        return glbls[name]
