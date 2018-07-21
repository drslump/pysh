"""
This package holds official code transformation modules.

A transformation module defines at least one of:

  - ``lexer(code: StringIO) -> StringIO``
  - ``parser(root: AST) -> AST``

Additionally the module symbols referenced on its ``__all__`` will
be made available as globals for the script. This allows to define
*runtime* functions on the generated code.

.. note:: The code AST is wrapped in a ``FunctionDef`` before calling
          a transformer parser. Transforms should expect a top level
          function wrapping the script code.
"""

import builtins
import ast
import logging
import re
from collections import ChainMap
from io import StringIO
from importlib import import_module
from types import FunctionType, CodeType

from typing import Union, Callable, Dict, List, Any


logger = logging.getLogger(__name__)


def _apply_transform(transform: Callable, obj: Any) -> Any:
    try:
        return transform(obj)
    except Exception as ex:
        import inspect  # lazy import
        raise RuntimeError(
            'Failed running {}.{} transform: {}'.format(
                inspect.getmodule(transform).__name__,
                transform.__name__,
                ex
            ))


class Compiler:
    """ Allows to register transform modules and obtain an executable
        function from some source code.
    """

    FALLBACK_PREFIXES = [
        'pysh_transform_',      # third party
        'pysh.transforms.',     # internal
    ]

    def __init__(self, transforms: List[str] = []):
        self.lexers = []
        self.parsers = []
        self.symbols = {}

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
                except ImportError:
                    logger.debug('Tried importing transform %s but failed', prefix + transform)

            if not module:
                logger.error('Unable to import transform %s', transform)
                raise RuntimeError('Unable to import transform {}'.format(transform))

        assert module, 'expected a valid module'
        #TODO: Warn if no lexer or parser was found

        if hasattr(module, 'lexer'):
            logger.debug('Registering lexer from %s', transform)
            self.lexers.append(getattr(module, 'lexer'))

        if hasattr(module, 'parser'):
            logger.debug('Registering parser from %s', transform)
            self.parsers.append(getattr(module, 'parser'))

        if hasattr(module, '__all__'):
            for symbol in getattr(module, '__all__'):
                logger.debug('Registering symbol %s from %s', symbol, transform)
                self.symbols[symbol] = getattr(module, symbol)

    def compile(self, code: StringIO, fname='<string>') -> Callable[[], Any]:
        """
        Given some script code it'll perform any configured transformation
        and return a function containing the compiled code. That function can
        be called to execute the script.
        """
        #TODO: a way to offset the positions when used as decorator
        #SEE: http://code.activestate.com/recipes/578353-code-to-source-and-back/

        for lexer in self.lexers:
            code = _apply_transform(lexer, code)

        node = ast.parse(code.read())

        # Now wrap the script in a function so we can get a reference to it.
        name = 'pysh_{}'.format(re.sub(r'\W', '_', fname))
        wrapper = ast.parse('def {}(): pass'.format(name))
        wrapper.body[0].body = node.body

        for parser in self.parsers:
            wrapper = _apply_transform(parser, wrapper)

        # Ensure locations are ok before compiling
        ast.fix_missing_locations(wrapper)
        comp = compile(wrapper, fname, 'exec')

        # Execute to trigger the creation of the wrapping function as a global
        glbls = dict(ChainMap(self.symbols, builtins.__dict__))
        exec(comp, glbls)

        return glbls[name]
