"""
Returns the last expression in a block, similarly to lambdas.

>>> def bar():
>>>     10
        return 10
>>> bar()
    return bar()

.. Note:: it won't transform statements like *if*, *for* or *while* into
          expressions that can be returned.
"""

from importlib import import_module
from ast import NodeTransformer, copy_location, fix_missing_locations, \
    AST, Module, FunctionDef, AsyncFunctionDef, Expr, Assign, Name, Store, Return


from typing import cast, Any, Union, Dict, List


class AutoReturnTransformer(NodeTransformer):

    def visit_Module(self, node: Module) -> Module:
        #TODO: DEPRECATED now that we wrap in a function before parsing
        self.generic_visit(node)

        if len(node.body) and isinstance(node.body[-1], Expr):
            #XXX requires hack on the main compile function
            node.body[-1] = Assign(
                targets=[Name(id='__autoreturn__', ctx=Store())],
                value=node.body[-1].value)
            fix_missing_locations(node.body[-1])

        return node

    def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef:
        self.generic_visit(node)

        if len(node.body) and isinstance(node.body[-1], Expr):
            node.body[-1] = Return(value=node.body[-1].value)
            fix_missing_locations(node.body[-1])

        return node

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> AsyncFunctionDef:
        casted = cast(FunctionDef, node)
        casted = self.visit_FunctionDef(casted)
        return cast(AsyncFunctionDef, casted)


def parser(node: AST) -> AST:
    return AutoReturnTransformer().visit(node)
