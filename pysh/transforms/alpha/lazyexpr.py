"""
Infers the requirement of a lambda by detecting which expressions use the
``?`` placeholder.

Only expressions in an assignment or in parameter positions are transformed.

>>> pipe.map( 'foo' + ?.lower() )
  # pipe.map( lambda __1, *args: 'foo' + __1.lower() )

TODO: Support multiple placeholders `?1 + ?2` -- `??` is whole varargs

"""

import ast
from io import StringIO

from pysh.transforms import TokenIO


PLACEHOLDER = '__INFERRED_LAMBDA_PLACEHOLDER__'


def lexer(code: StringIO) -> StringIO:
    """
    Lexer just replaces the ``?`` placeholder with something that doesn't
    make the Python parser chock up.
    """
    out = TokenIO()
    tokens = TokenIO(code).iter_tokens()
    for tkn in tokens:
        if tkn.string == '?':
            out.write_token(tkn, override=PLACEHOLDER)
        else:
            out.write_token(tkn)

    return out


class InferredLambdaTransformer(ast.NodeTransformer):

    def __init__(self):
        self.placeholder = PlaceholderTransformer()
        self.found = False

    def do_placeholder(self, node: ast.expr) -> ast.expr:
        self.placeholder.reset()
        node = self.placeholder.visit(node)
        if self.placeholder.replaced:
            node = ast.Lambda(
                args=ast.arguments(
                    args=[],
                    vararg=ast.arg(arg='__varargs'),
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[]),
                body=node,
                lineno=node.lineno,
                col_offset=node.col_offset)

            ast.fix_missing_locations(node)

        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id == PLACEHOLDER:
            self.found = True

        return node

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        self.found = False
        self.generic_visit(node)
        if self.found:
            node.value = self.do_placeholder(node.value)

        return node

    def visit_Call(self, node: ast.Call) -> ast.Call:
        self.found = False
        self.generic_visit(node)
        if self.found:
            node.args = [self.do_placeholder(x) for x in node.args]
            node.keywords = [(arg, self.do_placeholder(value)) for arg,value in node.keywords]

        return node


class PlaceholderTransformer(ast.NodeTransformer):

    def __init__(self):
        self.replaced = False

    def reset(self):
        self.replaced = False

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id == PLACEHOLDER:
            self.replaced = True
            node = ast.Subscript(
                value=ast.Name(id='__varargs', ctx=ast.Load()),
                slice=ast.Index(value=ast.Num(0)),
                ctx=ast.Load(),
                lineno=node.lineno,
                col_offset=node.col_offset)
            ast.fix_missing_locations(node)

        return node


class PlaceholderVisitor(ast.NodeVisitor):

    def __init__(self, fname):
        self.fname = fname

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id == PLACEHOLDER:
            from warnings import warn_explicit
            message = (
                'Detected an un-transformed lazyexpr `?` symbol. '
                'Only valid in assignments or argument positions. '
                '(from pysh.transform.alpha.lazyexpr)'
            ).format(id)

            warn_explicit(message, SyntaxWarning, self.fname, node.lineno)


def parser(node: ast.AST, fname: str) -> ast.AST:
    node = InferredLambdaTransformer().visit(node)
    PlaceholderVisitor(fname).visit(node)
    return node



code = '''\
print(list( map(?.lower(), ['Foo', 'Bar']) ))
'''

out = lexer(StringIO(code))
print(out.getvalue())

import ast, pprint
node = ast.parse(out.getvalue())
node = parser(node, '<code>')
print(ast.dump(node).replace("],", "\n],\n").replace('=[', '=[\n'))
co_code = compile(node, '<code>', 'exec')
exec(co_code)
