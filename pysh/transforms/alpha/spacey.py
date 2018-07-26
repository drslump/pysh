"""
Experimental transform for a removing some punctuation from *pysh* pipelines.

The rules are as follow (WS means is white space):

 - NAME [^ WS NEWLINE COMMENT ]+: capture all tokens until whitespace
 - if capture starts with MINUS (and len>1) then it's an option
 - if option has an EQUAL the left part is the name and the right a literal value
 - if capture contains path/glob/brace chars [/*?{] handle as path
 - else forward the captured tokens
 - in command mode handle whitespace as application << until NEWLINE/OR/XOR/LT/GT

cmd -h --verbose *.jpg 'filename.txt'
cmd << '-h' << '--verbose' << _[r'*.jpg'] << 'filename.txt'

in command mode everything is a literal except when parenthesis are found,
which are evaluated as a subexpression:

>>> cmd filename.txt (1+2)
    cmd['filename.txt'](1+2)
>>> cmd file.txt (ls *.jpg)
    cmd['file.txt'](ls['*.jpg'])
>>> age * 2
    age['*']['2'] ??!!
    # if it looks like a valid expression assume it is


Use ``--`` to dissambiguate:

    >>> ls *   # works because no right operand
    >>> ls /   # works because no right operand
    >>> ls -- * fname.txt  # after -- is a glob for sure
    >>> ls -- / fname.txt  # after -- is a path for sure

Variables:

    >>> echo (message)
    >>> ls -l (my_path) | wc -l



Alternative:

- NAME -[A-Z0-9-]+ -> starts command mode:
    - LPAR -> push command to stack, parse with command=False
    - RPAR -> pop command from stack, parse with command=True

>>> ls -l /
>>> ls -- *
>>> echo -- (ls -- * | grep -- 'foo') (my_file_var) fname.txt


"""

from io import StringIO

from tokenize import TokenInfo, ENDMARKER, NAME, OP, NEWLINE, COMMENT, \
    MINUS, STAR, DOUBLESTAR, SLASH, DOT, TILDE
from pysh.transforms import TokenIO, zip_prev, STARTMARKER


WS = -1

class WsTokenInfo(TokenInfo):
    def __repr__(self):
        return ('TokenInfo(type=%s, string=%r, start=%r, end=%r, line=%r)' %
                    self._replace(type='-1 (WS)'))


def tokens_with_space(tokens):
    for ptkn, ctkn in zip_prev(tokens):
        if ptkn and ctkn.type != ENDMARKER and ctkn.start > ptkn.end:
            yield WsTokenInfo(WS, ' ', ptkn.end, ctkn.start, ptkn.line)
        yield ctkn


def capture_until(tokens, until):
    captured = []
    tkn = None
    for tkn in tokens:
        if tkn.type in until:
            break
        captured.append(tkn)

    return captured, tkn

def is_option(tokens):
    if tokens[0].exact_type == MINUS:
        return len(tokens) > 1

    return False


def is_glob(tokens):
    has_tokens = any(
        t.exact_type in (STAR, DOUBLESTAR,)  # missing question mark
        for t in tokens)
    return has_tokens and len(tokens) > 1


def is_path(tokens):
    has_slash = any(t.exact_type == SLASH for t in tokens)
    has_dot = any(t.exact_type == DOT for t in tokens)
    has_tilde = tokens[0].exact_type == TILDE
    return has_slash or (has_dot or has_tilde) and len(tokens) > 1


def lexer(code: StringIO) -> StringIO:
    from pprint import pprint

    it = tokens_with_space(TokenIO(code))
    retry = None
    command = False
    while True:
        tkn = retry or next(it)
        if not command:
            pprint(tkn)
            if tkn.type == NAME:
                tkn = next(it)
                if tkn.type != WS:
                    print(tkn)
                    continue

                command = True

        captured, tkn = capture_until(it, (WS, NEWLINE, COMMENT, ENDMARKER))

        if is_option(captured):
            print('OPTION', ''.join(t.string for t in captured))
        elif is_glob(captured):
            print('GLOB', ''.join(t.string for t in captured))
        elif is_path(captured):
            print('PATH', ''.join(t.string for t in captured))

        retry = tkn
        command = tkn.type == WS
        pprint(captured)


code = r'''
cmd -- / path/to/filename.txt (bar (1+2))
#cmd -h --verbose
'''.strip()

lexer(code)