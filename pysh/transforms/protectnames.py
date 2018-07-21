"""
Detects shadowings of the ``_`` variable (used for *paths*), producing a
syntax error when detected.

Some programing styles use ``_`` as a way to ignore a result, which would
break the DSL.

.. note:: At some point this transformation should not report an error but
          rename the references to the protected name.
"""

from ast import NodeTransformer, AST, \
    Name, Assign, AugAssign, For, AsyncFor, Tuple, withitem, alias
from ast import AnnAssign  # type: ignore

from typing import Iterable


PROTECTED = ['_',]


class ProtectNamesTransformer(NodeTransformer):
    """ Shadowing of the given names is forbidden.
    """
    def __init__(self, names: Iterable[str]) -> None:
        self.names = set(names)

    def _check_target(self, target: AST, id: str = None) -> None:
        if not id:
            if isinstance(target, Name):
                id = target.id
            elif isinstance(target, Tuple):
                for n in target.elts:
                    self._check_target(n)
                return

        if id in self.names:
            #TODO: report position
            raise SyntaxError("Forbidden overwriting of name `{}`".format(id))

    def visit_Assign(self, node: Assign) -> Assign:
        for target in node.targets:
            self._check_target(target)

        self.generic_visit(node)
        return node

    def visit_AugAssign(self, node: AugAssign) -> AugAssign:
        self._check_target(node.target)
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node: AnnAssign) -> AnnAssign:
        self._check_target(node.target)
        self.generic_visit(node)
        return node

    def visit_For(self, node: For) -> For:
        self._check_target(node.target)
        self.generic_visit(node)
        return node

    def visit_AsyncFor(self, node: AsyncFor) -> AsyncFor:
        self._check_target(node.target)
        self.generic_visit(node)
        return node

    def visit_withitem(self, node: withitem) -> withitem:
        if node.optional_vars:
            self._check_target(node.optional_vars)
        self.generic_visit(node)
        return node

    def visit_alias(self, node: alias) -> alias:
        if node.asname:
            self._check_target(node, id=node.asname)
        else:
            self._check_target(node, id=node.name)
        return node


def parser(node: AST) -> AST:
    return ProtectNamesTransformer(PROTECTED).visit(node)
