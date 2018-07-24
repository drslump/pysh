from io import StringIO
import re
import tokenize
import os
from collections import deque, ChainMap
from functools import lru_cache
from enum import Enum

import pysh
from pysh.path import PathWrapper, Path

from typing import List, Callable, Iterator, Tuple, NamedTuple, Deque, Union, Any
TBangTransformer = Callable[ [List[str]], Iterator[str]]


# runtime symbols
__all__ = ['BangExpr', 'BangOp', 'BangSeq', 'BangGlob', 'BangEnv', 'BangBang']


class BangTokenType(Enum):
    OPAQUE = 'OPAQUE'
    GLOB = 'GLOB'
    LOCAL = 'LOCAL'
    ENV = 'ENV'
    EXPR = 'EXPR'
    OP = 'OP'


class BangToken(NamedTuple):
    type: BangTokenType
    value: str
    span: Tuple[int, int]


TBangLexerToken = Tuple[str, str, Tuple[int,int]]
class BangLexer:

    def _tokener(self, token, transformer=lambda x: x, **kwargs):
        def cb(s, v):
            v = transformer(v, **kwargs)
            return None if v is None else (token, v, (s.match.start(), s.match.end()))
        return cb

    @lru_cache()  # it's intended for this to be global
    def build_scanner(self):
        t = self._tokener
        return re.Scanner([
            (r'\#.+', t('COMMENT', lambda v: v[1:])),
            (r'\\.', t('ESCAPE')),
            (r"'( \\. | [^\\']+ )+'", t('SQS', lambda v: v[1:-1])),
            (r'"( \\. | [^\\"]+ )+"', t('DQS', lambda v: v[1:-1])),
            (r'\$[A-Za-z_][A-Za-z0-9_]*', t('VAR', lambda v: v[1:])),
            (r'\${( \\. | [^\\}]+ )+}', t('EXPR', lambda v: v[2:-1])),
            (r'[|<>^]+', t('OP')),
            (r'[A-Za-z0-9_%*+:.,=/@~\[\]{}-]+', t('OPAQUE')),
            (r'\s+', t('WS')),
        ], flags=re.X)

    @lru_cache()
    def build_dqs_scanner(self):
        t = self._tokener
        return re.Scanner([
            (r'\\.', t('ESCAPE')),
            (r'\$[A-Za-z_][A-Za-z0-9_]*', t('VAR', lambda v: v[1:])),
            (r'\${( \\. | [^\\}]+ )+}', t('EXPR', lambda v: v[2:-1])),
            (r'[^\\\$]+', t('SQS'))  # handle as single quoted
        ], flags=re.X)

    def scan_dqs(self, code: str, offset=0) -> Iterator[TBangLexerToken]:
        tokens, remaining = self.build_scanner().scan(code)
        if remaining:
            raise SyntaxError('Unexpected char <{}> at position {}'.format(remaining[0], len(code)-len(remaining)))

        for tkn, val, pos in tokens:
            yield tkn, val, (offset+pos[0], offset+pos[1])

    def demux_dqs(self, tokens: Iterator[TBangLexerToken]) -> Iterator[TBangLexerToken]:
        """ Split double quoted strings into parts
        """
        for tkn, val, pos in tokens:
            if tkn == 'DQS':
                yield from self.scan_dqs(val, offset=pos[0]+1)
            else:
                yield tkn, val, pos

    def scan(self, code: str) -> Iterator[BangToken]:
        tokens, remaining = self.build_scanner().scan(code)
        if remaining:
            raise SyntaxError('Unexpected char at position {}'.format(len(code)-len(remaining)))

        # Add a terminating token so we can simplify the parsing
        tokens.append(('END', '', (len(code),len(code))))

        last_token = last_pos = None
        for token, value, pos in self.demux_dqs(tokens):
            assert token != 'DQS'  # double quoted are demuxed

            # Inject whitespace operator if needed
            if token != 'OP' and last_token and last_token == 'WS':
                yield BangToken(BangTokenType.OP, ' ', last_pos)

            if token in ('COMMENT', 'END'):
                continue
            elif token == 'WS':
                pass
            elif token == 'OP':
                value = value.strip()
                yield BangToken(BangTokenType.OP, value, pos)
            else:
                if token == 'OPAQUE':
                    if re.search(r'(?!<\\)[~*?{]', value):
                        yield BangToken(BangTokenType.GLOB, value, pos)
                    else:
                        yield BangToken(BangTokenType.OPAQUE, value, pos)
                elif token in ('ESCAPE', 'SQS'):
                    #TODO: handle special escapes \n
                    value = re.sub(r'\\(.)', r'\1', value)
                    yield BangToken(BangTokenType.OPAQUE, value, pos)
                elif token in ('VAR', 'EXPR'):
                    value = value.strip()
                    if value.isalnum() and not value.isdigit():
                        if value.isupper():
                            yield BangToken(BangTokenType.ENV, value, pos)
                        else:
                            yield BangToken(BangTokenType.LOCAL, value, pos)
                    else:
                        assert token == 'EXPR'
                        value = re.sub(r'\\(.)', r'\1', value)
                        yield BangToken(BangTokenType.EXPR, value, pos)
                else:
                    assert False, 'unexpected {}, what happened?'.format(token)

            last_token, last_pos = token, pos


class BangEnv:
    __slots__ = ('name',)
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'BangEnv<{}>'.format(self.name)

class BangSeq:
    __slots__ = ('items',)
    def __init__(self, *items):
        self.items = items

    def __repr__(self):
        return 'BangSeq<{!r}>'.format(self.items)

class BangOp:
    __slots__ = ('op',)
    def __init__(self, op):
        self.op = op

    def __repr__(self):
        return 'BangOp<{}>'.format(self.op)

class BangGlob:
    __slots__ = ('glob',)
    def __init__(self, glob):
        self.glob = glob

    def __repr__(self):
        return 'BangGlob<{}>'.format(self.glob)


class BangExpr:
    __slots__ = ('args', 'vars')

    def __init__(self, *args, locals=None, globals=None):
        assert locals is not None
        assert globals is not None
        self.args = args
        self.vars = ChainMap(locals, globals)

    def eval_command(self, mut_args):
        arg = mut_args.popleft()
        cmd = self.vars.get(str(arg))
        if cmd is None:
            raise RuntimeError('Unable to find {}'.format(arg))

        while mut_args:
            if isinstance(mut_args[0], BangOp):
                break

            arg = mut_args.popleft()
            cmd = cmd(self.eval_expr(arg))

        return cmd

    def eval_expr(self, expr: Any) -> Union[str, Iterator[Path]]:
        if isinstance(expr, BangSeq):
            return self.eval_seq(expr)
        elif isinstance(expr, BangEnv):
            return os.environ[expr.name]
        elif isinstance(expr, BangGlob):
            return PathWrapper().glob(expr.glob)
        else:
            return str(expr)

    def eval_seq(self, seq: BangSeq) -> Union[str, Iterator[Path]]:
        exprs: Deque[Any] = deque(seq.items)
        accum = ''
        while exprs:
            expr = exprs.popleft()

            if isinstance(expr, BangGlob):
                if exprs:
                    raise RuntimeError('Globbing can only occur at the end of a seq')
                return PathWrapper(accum).glob(expr.glob)

            accum += self.eval_expr(expr)

        return accum

    def eval(self):
        mut_args = deque(self.args)

        cmd = self.eval_command(mut_args)
        while mut_args:
            arg = mut_args.popleft()
            assert isinstance(arg, BangOp), 'Expected OP but found: {}'.format(arg)
            assert len(mut_args) > 0, 'No operands left!'
            if arg.op == '|':
                cmd |= self.eval_command(mut_args)
            elif arg.op == '^':
                cmd ^= self.eval_command(mut_args)
            elif arg.op == '>':
                cmd = cmd > self.eval_expr(mut_args.popleft())
            elif arg.op == '>>':
                cmd = cmd >> self.eval_expr(mut_args.popleft())
            else:
                raise RuntimeError('Unsupported operator {}'.format(arg.op))

        return cmd

    def __str__(self):
        return str(self.eval())

    def __repr__(self):
        return 'BangExpr<{!r}>'.format(self.args)


class BangBang:
    __slots__ = ('code',)

    def __init__(self, code):
        self.code = code

    def eval(self):
        #TODO: Detect shebang and use it instead of default shell
        import sys, subprocess
        result = subprocess.run(
            ['bash', '-c', self.code],
            encoding='utf-8',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode > 0:
            if result.stdout:
                print(result.stdout)
            raise pysh.ExitStatusError(result.returncode)

        return result.stdout

    def __str__(self):
        return str(self.eval())

    def __repr__(self):
        return 'BangBang<{}>'.format(self.code)


def parse_bangexpr(code: str) -> str:

    as_str = lambda s: "'{}'".format(s.replace("\\", "\\\\").replace("'", "\\'"))

    lexer = BangLexer().scan(code)
    seq = []
    exprs = []
    while True:
        tkn = next(lexer, None)
        if tkn and tkn.type != BangTokenType.OP:
            if tkn.type in (BangTokenType.LOCAL, BangTokenType.EXPR):
                seq.append(tkn.value)
            elif tkn.type == BangTokenType.ENV:
                seq.append('pysh.BangEnv({})'.format(as_str(tkn.value)))
            elif tkn.type == BangTokenType.OPAQUE:
                seq.append('{}'.format(as_str(tkn.value)))
            elif tkn.type == BangTokenType.GLOB:
                seq.append('pysh.BangGlob({})'.format(as_str(tkn.value)))
            else:
                assert False, 'Unexpected token {}'.format(tkn.type)

            continue

        if seq:
            if len(seq) > 1:
                exprs.append('pysh.BangSeq({})'.format(', '.join(seq)))
            else:
                exprs.append(seq[0])
            seq = []

        if not tkn:
            break

        assert tkn.type == BangTokenType.OP
        if tkn.value ==  ' ':
            continue

        exprs.append('pysh.BangOp("{}")'.format(tkn.value))

    # We need to provide locals/globals so we can resolve commands to variables
    return 'pysh.BangExpr({}, locals=locals(), globals=globals())'.format(', '.join(exprs))


def transform(code: StringIO, transformer: TBangTransformer) -> Iterator[str]:
    """ Scans python code to transform bang expressions.

        Given some python code it will extract bang expressions and process
        them with a callback that can report back the transformation.

        Returns a generator that allows to consume the transformed code
        line by line.
    """
    tokens = tokenize.generate_tokens(code.readline)

    bangexpr = []  # type: List[str]
    bangcont = False
    prebang = None
    ptkn = None
    indent = 0
    bang_indent = -100
    last_bang_line = -100
    for ctkn in tokens:

        if ctkn.type == tokenize.INDENT:
            indent += 1
            if last_bang_line + 1 == ctkn.start[0]:
                bang_indent = indent
        elif ctkn.type == tokenize.DEDENT:
            indent -= 1
            if bang_indent > indent:
                bang_indent = -100

        # due to continuations we can't rely on NEWLINE tokens, instead we have
        # use the lexical information to detect when we're on a new line
        #TODO: Support indent/dedent for multiline
        if ptkn and ctkn.start[0] > ptkn.start[0]:
            if bangcont or bang_indent == indent:
                if ctkn.type is tokenize.ENDMARKER:
                    raise SyntaxError('BangExpr continuation at program end')

                line = ctkn.line.rstrip('\r\n')
                bangexpr.append(line)
                bangcont = line.endswith('\\')
                last_bang_line = ctkn.start[0]
            elif bangexpr:
                lines = list(transformer(bangexpr))
                assert len(lines) <= len(bangexpr)
                if lines and prebang:
                    lines[0] = prebang + lines[0]

                yield from lines
                bangexpr = []
                last_bang_line = ptkn.start[0]
            else:
                yield ptkn.line

        ptkn = ctkn

        if bangexpr:
            continue

        if ctkn.string == '!':
            col = ctkn.start[1]
            prebang = ctkn.line[0:col]
            line = ctkn.line[col+1:].lstrip(' \t').rstrip('\r\n')
            bangexpr.append(line.rstrip('\\'))
            bangcont = line.endswith('\\')
            last_bang_line = ctkn.start[0]

    assert not bangexpr, bangexpr


def transformer(lines: List[str]) -> Iterator[str]:
    if lines[0].startswith('!'):
        #TODO: Detect $ident to expose them on env when evaluated
        lines[0] = lines[0][1:]
        code = '\n'.join(lines)
        code = code.strip().replace("'", "\\'").replace("\\", "\\\\")
        code = "pysh.BangBang('{}')".format(code)
        lines = code.split('\n')
        for line in lines:
            yield line

    else:

        yield from parse_bangexpr(' '.join(lines)).split('\n')


from io import StringIO
code = r'''
foo = ! ls foo${bar}.* \
        | grep foo
        > /dev/null
foo = r' ls foo${bar} ' >> expr
expr<' ls foo${bar} '

!!  #!/bin/fish
    ls .*
'''.strip()

#TODO: !! is probably better solved with:
# locals are solved with inspect.frame.f_locals
sh << r'''
    # << means with variables interpolated
    # < is plain text
    ls .*
'''

for line in transform(StringIO(code), transformer):
    print(line.rstrip('\n'))

from pysh.command import command

ls = command('ls')
grep = command('grep')
bar = 10

print('::BangExpr::')
be = BangExpr('ls', BangSeq('foo', bar, BangGlob('.*')), BangOp("|"), 'grep', 'foo', 'baz', BangOp(">"), '/dev/null', locals=locals(), globals=globals())
# print(be)

print('::BangBang::')
bb = BangBang('''#!/bin/bash
    ls *.py''')
print(bb)