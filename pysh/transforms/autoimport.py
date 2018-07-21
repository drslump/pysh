"""
Every name reference is swapped for a call to ``__autoimport__``, which
will check if it's part of the locals or globals, falling back to trying
an import before giving up.
"""

from importlib import import_module
from ast import NodeTransformer, copy_location, fix_missing_locations, \
    AST, Call, Name, Load, Str, keyword


from typing import Any, Union, Dict


__all__ = ['__autoimport__']


class AutoImportTransformer(NodeTransformer):

    def visit_Name(self, node: Name) -> Union[Name, Call]:
        if not isinstance(node.ctx, Load):
            return node

        delegate = Call(
            func=Name(id='__autoimport__', ctx=Load()),
            args=[
                Str(s=node.id)
            ],
            keywords=[])

        copy_location(delegate, node)
        fix_missing_locations(delegate)
        return delegate


def __autoimport__(name: str) -> Any:
    import inspect
    f_back = inspect.currentframe().f_back  #type: ignore

    if name in f_back.f_locals:
        return f_back.f_locals[name]

    if name in f_back.f_globals:
        return f_back.f_globals[name]

    try:
        return import_module(name)
    except ImportError:
        pass

    raise NameError(name)


def parser(node: AST) -> AST:
    return AutoImportTransformer().visit(node)
