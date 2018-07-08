from collections import defaultdict
from pysh import autoimport

def argparse(argv):
    """ Simple system to parse arguments into a dictionary

        - short options can be grouped `-abc`
        - options have their value after `=`
        - `--` stops interpreting options
        - anything else is an argument under `*`
    """
    result = defaultdict(lambda: [])
    result['*'] = []

    parse_options = True
    for arg in argv:
        if parse_options:
            if arg == '--':
                parse_options = False
                continue

            parts = arg.split('=', 2)
            if arg.startswith('--'):
                result[parts[0]].append(True if len(parts) < 2 else parts[1])
                continue
            elif arg.startswith('-'):
                for ch in parts[0][1:]:
                    result['-' + ch].append(True)

                if len(parts) > 1:
                    result['-' + parts[0][-1]][-1] = parts[1]

                continue

        result['*'].append(arg)

    return dict(result)




def unbangbang(script):
    """ Transforms !! expressions.
        Since this is an optional step we have deferred imports.
    """
    import tokenize
    from collections import deque
    import shlex
    import six

    io = six.io.StringIO(script)
    g = tokenize.generate_tokens(io.readline)

    accum = deque()
    bang = None
    ptkn = None
    ctkn = next(g, None)
    while ctkn:
        if bang:
            if ctkn.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                # tokenizer doesn't report white space but we need to fully respect
                # it. So get the the only option is to get the lexical information from the
                # tokens and extract the actual text from the file.
                lines = []
                last_line = 0
                while accum:
                    tkn = accum.popleft()
                    if tkn.start[0] > last_line:
                        last_line = tkn.start[0]
                        if not lines:
                            lines.append(tkn.line[tkn.start[1]:])
                        else:
                            lines.append(tkn.line)

                expr = ''.join(lines).rstrip()
                print(expr)

                #TODO: transform expr into tokens
                # expr = shlex.split(expr, comments=True)
                scanner = shlex.shlex(expr, posix=True)
                scanner.whitespace_split = True
                while True:
                    # in posix mode the scanner will not return the quotes
                    # so it's not possible to tell apart `|` from `"|"`. As
                    # a hack we obtain the current offset in the stream so
                    # we can manually check what's the first character.
                    ofs = scanner.instream.tell()
                    tkn = scanner.get_token()
                    if not tkn:
                        break

                    print('{} [{}]'.format(tkn, expr[ofs]))

                tokens = (
                    (tokenize.NAME, 'foo'),
                    (tokenize.LPAR, '('),
                    (tokenize.STRING, '"-o"'),
                    (tokenize.COMMA, ','),
                    (tokenize.NAME, 'env'),
                    (tokenize.LSQB, '['),
                    (tokenize.STRING, '"O"'),
                    (tokenize.RSQB, ']'),
                    (tokenize.COMMA, ','),
                    (tokenize.STRING, '"--opt"'),
                    (tokenize.COMMA, ','),
                    (tokenize.STRING, '"|"'),
                    (tokenize.RPAR, ')'),

                    (tokenize.OP, '|'),

                    (tokenize.NAME, 'cat'),

                    (tokenize.OP, '>>'),
                    (tokenize.STRING, '"foo.txt"')
                )
                line = bang.start[0]
                col = bang.start[1]
                for ident, value in tokens:
                    yield (ident, value, (line, col), (line, col + len(value)), bang.line)
                    col += len(value)
                    if ident in (tokenize.COMMA,):
                        col += 1

                bang = None
                # update lexical info to make sure it comes after the transform
                yield (ctkn.type, ctkn.string, (line, col), (line, col + len(ctkn.string)), ctkn.line)
            else:
                accum.append(ctkn)

        elif ctkn.type == tokenize.ERRORTOKEN:
            if ctkn.string == '!' and ptkn and ptkn.string == '!':
                accum.pop()  # discard previous bang
                while accum: yield accum.popleft()
                bang = ptkn
            elif not ctkn.string.isspace():  #XXX not sure why spaces are given before !!
                accum.append(ctkn)
        else:
            while accum: yield accum.popleft()
            yield ctkn

        ptkn = ctkn
        ctkn = next(g, None)


# s = r'''
# a = !! foo -o $O --opt '|' | cat >> foo.txt
# b = 10
# '''

# import tokenize
# print(tokenize.untokenize(unbangbang(s)))


# import sys
# print(argparse(sys.argv[1:]))


# print(command_mode('if random.randint(1, 10) > 3: return 10'))