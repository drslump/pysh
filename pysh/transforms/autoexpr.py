"""
Auto Expressions is a tranformation of Python source code that detects
every statement that only holds an expression (i.e. no assigments) and
wraps them in a function call.

This allows at runtime to obtain the value from an statement and have
semantics closer to a command oriented language.

>>> foo | bar
    __autoexpr__( foo | bar )

>>> a = foo | bar
    a = foo | bar
"""

from ast import NodeTransformer, fix_missing_locations, AST, \
    FunctionDef, AsyncFunctionDef, ClassDef, Expr, Call, Name, Load

from pysh.command import CommandBuilder

from typing import Any


__all__ = ['__autoexpr__']


class AutoExprTransformer(NodeTransformer):
    """ Every Expr node is wrapped with a call to a function.
        Except inside classes.
    """
    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        return node

    def visit_Expr(self, node: Expr) -> Expr:
        node.value = Call(
            func=Name(id='__autoexpr__', ctx=Load()),
            args=[node.value],
            keywords=[]
        )

        fix_missing_locations(node)
        return node


def __autoexpr__(value: Any) -> Any:
    """ Every Expr node will be passed as an argument to this function.
        It should inspect the value and act upon it.
    """
    if isinstance(value, CommandBuilder):
        return value.invoke()

    return value


def parser(node: AST) -> AST:
    return AutoExprTransformer().visit(node)
