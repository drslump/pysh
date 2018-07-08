"""
Command mode tooling.

This module should not be exposed via the package, it's only for
the command line runner so we can skip its loading if possible.

Transforms some code so that:

 - it automatically imports packages
 - last expression is returned

"""
from functools import partial
from ast import NodeTransformer, Load, Store, Name, Str, Assign, Call, Raise, \
                parse, copy_location, fix_missing_locations


AUTOIMPORT = '__autoimport__'
ASSIGN_RETURN = '__return__'
RAISE_RETURN = '__Return__'


class CommandModeTransformer(NodeTransformer):
    """
    Every top level name reference is swapped for a call to autoimport,
    which will check if it's part of the locals or builtins, falling back
    to trying an import before giving up.

    Since returns are not allowed at _module_ level we replace them with
    a custom raised error to signal the value.

    Every expression-statement (Expr) gets transformed into an assigment
    to ASSIGN_RETURN, when the code terminates we just return the value
    assigned in that local.
    """

    def visit_Name(self, node):
        if not isinstance(node.ctx, Load):
            return node

        delegate = Call(
            func=Name(id=AUTOIMPORT, ctx=Load()),
            args=[
                Str(s=node.id)
            ],
            keywords=[]
        )

        copy_location(delegate, node)
        fix_missing_locations(delegate)
        return delegate

    def visit_Expr(self, node):
        self.visit(node.value)

        delegate = Assign(
            targets=[
                Name(id=ASSIGN_RETURN, ctx=Store())
            ],
            value=node.value
        )

        copy_location(delegate, node)
        fix_missing_locations(delegate)
        return delegate

    def visit_Return(self, node):
        self.visit(node.value)

        delegate = Raise(
            exc=Call(
                func=ast.Name(id=RAISE_RETURN, ctx=Load()),
                args=[node.value],
                keywords=[]
            ),
            cause=None
        )

        copy_location(delegate, node)
        fix_missing_locations(delegate)
        return delegate


class RaisedReturn(Exception):
    def __init__(self, value):
        self.value = value


def autoimport(builtins, locals, name):
    if name in locals:
        return locals[name]

    if hasattr(builtins, name):
        return getattr(builtins, name)

    import importlib  # deferred import
    try:
        return importlib.import_module(name)
    except ImportError:
        pass

    raise NameError(name)


def execute(code):
    """ Execute the given code after transforming it to support autoimports
    """
    node = parse(code)
    node = CommandModeTransformer().visit(node)

    code = compile(node, '<string>', 'exec')

    try:
        import builtins
    except ImportError:
        import __builtin__ as builtins

    lcls = {ASSIGN_RETURN: None}
    glbls = {
        AUTOIMPORT: partial(autoimport, builtins, lcls),
        RAISE_RETURN: RaisedReturn
    }

    try:
        exec(code, glbls, lcls)
    except RaisedReturn as ret:
        return ret.value

    assert ASSIGN_RETURN in lcls
    return lcls[ASSIGN_RETURN]


def execute_and_exit(code):
    """ Execute the code and exit according to:
        - False: exitcode 1
        - None/True: exitcode 0
        - Else: print it and exitcode 0
    """
    result = execute(code)
    if result is False:
        raise SystemExit(1)

    if result is not True and result is not None:
        print('{}'.format(result))

    raise SystemExit(0)


if __name__ == '__main__':
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    execute_and_exit(code)
