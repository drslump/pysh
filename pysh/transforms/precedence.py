"""
Modifies operator binding precedence for ``<`` and ``>`` to emulate those found
in a *sh* based shell.


.. Danger::
    The transformation not only applies to *pysh* expressions but to
    **all the expressions** using those operators in the script. For
    most uses it should be transparent but there is always the risk
    of introduce unexpected behaviour in what would be totally valid
    Python code.


Here is a table listing the binding precedence for the operators used in the
DSL, from lower to higher, comparing those of Python with the ones in a shell:

======================  =================================
        Python                        Sh
======================  =================================
     ``<`` ``>``                     ``|``
        ``|``            ``^`` ``<`` ``>`` ``<<`` ``>>``
        ``^``
    ``<<`` ``>>``
======================  =================================

In a shell all *redirections* share the same precedence so they are naturaly
evaluated (left associative), however in Python different *redirection* operators
have different binding precedece and more importantly, the pipe operator ``|``
has a higher precedence than the normal redirections.

For simple expressions it doesn't really matter, the DSL can be designed to
dissambiguate common use cases, however once the expression is a bit more complex
having the correct binding precedence is critical, otherwise the programmer is
forced to use parenthesis to enforce the correct meaning.

Take for instance the following example where we want to ignore the *stdout* from
a command and do a pipeline from its *stderr*:

>>> cmd >null ^stdout | bar >null
python: ( cmd > ( ( null ^ stdout ) | bar ) ) > null
 shell: ( ( cmd > null ) ^ stdout ) | ( bar  > null )

With standard Python operator precedence the expression would fail, or even worse,
in some scenarios it might have worked but not doing what the programmer intended.
A possible solution would be for the programmer to use parenthesis or reorder some
operators to make sure it does what she wants:

>>> (cmd ^stdout >null) | bar >null

This transformation offers another solution, it changes the binding precedence of
the ``>`` and ``<`` operators when parsing a script. Note that this means that
**it's changed for commands but also for any other value in the code**, the
assumption here is that since the precedence problem only happens when chaining
operators and given that most of the operators used are not commonly chained in
plain Python code, it's best for the script to use shell-like precedences for the
whole script. The final binding precedence table is as follows (lower to higher):

======================  ========================
        Python                   pysh
======================  ========================
     ``<`` ``>``                 ``|``
        ``|``              ``^`` ``>`` ``<``
        ``^``                ``<<`` ``>>``
    ``<<`` ``>>``
======================  ========================


The implementation is quite a hack though, in order to keep it simple we want
to leverage the Python parsing infrastructure as much as possible instead of
creating our own parser with different binding precedences. We abuse the fact
that the two operators we want to change should have the same one as the bitwise
operator ``^``, mapping the redirections to it so we can keep the rest of operators
unchanged. While that mapping ensures the correct parsing we need to *annotate*
somehow the original operator, for that we rely on some runtime helpers and the
use of ``&``, which has slightly higher binding precedence than ``^``, this is
merely a trick to avoid having to detect whole expressions boundaries at the lexer
level as to wrap them in a call to the runtime helper, instead the parser will do
that for us automatically and then it uses the ``__and__`` overload.

>>> fname < cmd ^ stdout | head > 'errors.txt'
    fname ^LT& cmd ^ stdout | head ^GT& 'errors.txt'
    ( (fname ^ (LT & cmd)) ^ stdout ) | ( head ^ (GT & 'errors.txt') )

The approach has the benefit that the common pipe operator is unchanged, so it has
no runtime cost. For the ``<`` and ``>`` operators first the helper's bitwise
``__and__`` will be called so it can obtain the right-hand operand, then it returns
an instance with a ``__rxor__`` overload suitable to perform the original operation
when Python evaluates the injected ``^`` operator.

>>> cmd > null
    cmd ^ (GT & null)
    GT.__and__(null).__rxor__(cmd) => cmd > null


.. Warning::
    if the code being transformed uses numerical bitwise operators or classes
    that overload them the results might be unexpected. The whole system relies
    on working with standard types and the *pysh* DSL types.

    The same applies to *chained comparisons*, althought some of those cases are
    detected and a syntax warning is issued pointing out the problematic use.

"""

from io import StringIO
from tokenize import OP
from ast import walk, AST, Compare

from pysh.transforms import TokenIO


__all__ = ['__PYSH_LT__', '__PYSH_GT__']


class AndCapturer:
    """
    Base runtime helper for an operator.

    Note that this abuses the fact that ``__and__`` and ``__rxor__`` will be
    called in quick succession for the same operation. This assumption allows
    to reuse the same instance for each modified operator in the script, which
    saves memory and time.
    """
    __slots__ = ('rhs',)

    def __and__(self, rhs):
        """ Captures the rhs value.
        """
        self.rhs = rhs
        return self


class LessThanResolver(AndCapturer):
    def __rxor__(self, lhs):
        return lhs < self.rhs

    def __repr__(self):
        return '<{!r}'.format(self.rhs)


class GreaterThanResolver(AndCapturer):
    def __rxor__(self, lhs):
        return lhs > self.rhs

    def __repr__(self):
        return '>{!r}'.format(self.rhs)


# Create the runtime helpers
__PYSH_LT__ = LessThanResolver()
__PYSH_GT__ = GreaterThanResolver()


OPS_HACK = {
    '<': '^__PYSH_LT__&',
    '>': '^__PYSH_GT__&',
}


def lexer(code: StringIO, *, fname=None) -> StringIO:
    out = TokenIO()
    for tkn in TokenIO(code).iter_tokens():
        if tkn.type == OP and tkn.string in OPS_HACK:
            out.write_token(tkn, override=OPS_HACK[tkn.string])
        else:
            out.write_token(tkn)

    return out


def parser(node: AST, *, fname: str) -> AST:
    """ TODO: right now only comparisons like ``10 <= 20 <= 30`` are detected,
              since the lexer converts ``< >`` to ``^`` the parser AST does not
              reflect a potential chaining. So the usefulness of this check is
              not great. If no solution is found to detect the use of ``<`` in
              chained comparisons then this check should probably be removed.

              Probably the best solution would be for the AndCapturer to be moved
              into a parser transform instead of working at the runtime. That way
              it'll be simpler to detect those cases.
    """
    for n in walk(node):
        if not isinstance(n, Compare) or len(n.ops) == 1:
            continue

        from warnings import warn_explicit
        message = (
            'Chained comparisons might yield unexpected results in pysh scripts '
            'since, unlike standard Python code, operators `<` and `>` have the '
            'same binding precedence as the bitwise `^` operator. Please '
            'consider changing the expression to its unchained form with the '
            '`and` boolean operator. (from pysh.transform.precedence)'
        )
        warn_explicit(message, SyntaxWarning, fname, n.lineno)

    return node



if __name__ == '__main__':
    code = '''
# cmd > null ^ stdout | bar >> fname | baz
# if foo < 10:
    # pass

_ / 'foo' ** '*.jpg'

    '''.strip()

    out = lexer(StringIO(code))
    print(out.getvalue())

    from ast import parse
    node = parse(code) #out.getvalue())
    parser(node, fname='test.py')


