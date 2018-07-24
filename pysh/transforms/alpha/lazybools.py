"""
In Python it's not possible to overload the boolean operators (``not``,
``and``, ``or``) since they have short-circuiting semantics (PEP-532 is
deferred right now).

The problem manifests when trying to use a ``cmd and ok or fail``
or similar constructs, which are quite common in shell scripts. We would
like to keep that expression lazily evaluated but is not possible since
the Python interpreter will try to resolve it immediately, trigering the
evaluation of ``cmd`` to know if it should go with the ``and`` or the ``or``
branch.

This tranformation converts the above example to:

>>> OR(AND(cmd, lambda: ok), lambda: fail)

Where ``OR`` and ``AND`` are runtime helpers that will inspect the value
and delegate to it if it has defined the proper protocol:

  - ``__lazyboolnot__(self)``
  - ``__lazybooland__(self, rhs_callable)``
  - ``__lazyboolor__(self, rhs_callable)``

.. note:: These operators do not have a reverse, the argument will always
          be the right operand.

.. caution:: Since the rhs is opaque inside the lambda, we can't check it
             until it resolves.

"""

from ast import NodeTransformer, copy_location, fix_missing_locations, AST, \
    BoolOp, UnaryOp, And, Or, Not, Call, Lambda, arguments, Name, Load

from typing import Union


__all__ = ['__lazybooland__', '__lazyboolor__', '__lazyboolnot__']


class LazyBoolsTransformer(NodeTransformer):
    """ Make logical operators aware of laziness.
    """
    def visit_BoolOp(self, node: BoolOp) -> Union[UnaryOp, Call]:
        self.generic_visit(node)

        if isinstance(node.op, And):
            runtime = '__lazybooland__'
        elif isinstance(node.op, Or):
            runtime = '__lazyboolor__'
        else:
            return node

        lhs, rhs = node.values
        delegate = Call(
            func=Name(id=runtime, ctx=Load()),
            args=[
                lhs,
                # Make the rhs a deferred computation by wrapping with a lambda
                Lambda(
                    args=arguments(args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                    body=rhs)
            ],
            keywords=[])

        copy_location(delegate, node)
        fix_missing_locations(delegate)
        return delegate

    def visit_UnaryOp(self, node: UnaryOp) -> Union[UnaryOp, Call]:
        self.generic_visit(node)

        if not isinstance(node.op, Not):
            return node

        delegate = Call(
            func=Name(id='__lazyboolnot__', ctx=Load()),
            args=[node.operand],
            keywords=[])

        copy_location(delegate, node)
        fix_missing_locations(delegate)
        return delegate


def __lazybooland__(expr, deferred):
    if hasattr(expr, '__lazybooland__'):
        result = expr.__lazyand__(deferred)
        if result is not NotImplemented:
            return result

    return expr and deferred()

def __lazyboolor__(expr, deferred):
    if hasattr(expr, '__lazyboolor__'):
        result = expr.__lazyor__(deferred)
        if result is not NotImplemented:
            return result

    return expr or deferred()

def __lazyboolnot__(expr):
    if hasattr(expr, '__lazyboolnot__'):
        result = expr.__lazynot__()
        if result is not NotImplemented:
            return result

    return not expr


def parser(node: AST) -> AST:
    return LazyBoolsTransformer().visit(node)



from ast import parse, dump

# print(dump(parse('lambda: 10')))
cmd = 0
ok = 'ok'
fail = 'fail'
node = parse(r'''
print( cmd and ok or not fail )
''')

node = parser(node)
print(dump(node))

co_code = compile(node, '<string>', 'exec')
eval(co_code, globals())
