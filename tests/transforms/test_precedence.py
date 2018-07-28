from functools import partial
import pytest

from pysh.transforms import precedence
from pysh.dsl import Pipeline, Redirect, Command, Pipe, Piperr

from .utils import factory


lex, parse, comp, auto = factory(precedence)


def test_cmd_gt_value():
    assert lex('cmd > fname') == 'cmd ^__PYSH_GT__& fname'

def test_value_lt_cmd():
    assert lex('fname < cmd') == 'fname ^__PYSH_LT__& cmd'

def test_chaining_redirects_no_warning(recwarn):
    comp('10 > 20 > 30')
    assert len(recwarn) == 0

def test_chaining_comparisons_warns():
    with pytest.warns(SyntaxWarning):
        comp('10 <= 20 <= 30')

@pytest.mark.skip('not detected yet')
def test_chaining_comparisons_and_redirects_warns():
    with pytest.warns(SyntaxWarning):
        comp('10 < 20 <= 30')

def test_comparisons_with_values():
    assert auto('10 > 5 and 5 < 10') is True
    assert auto('10 > 5 < 10') is True
    assert auto('1 < 2 < 3 <= 3') is True

def test_pipeline_bind_redirects():
    expr = auto('''\
        cmd = command('cat')
        expr = '/dev/null' < cmd ^ 'errors.txt' | cmd > 'output.txt'
        return expr
    ''')
    #print(repr(expr))

    # We expect the following grouping:
    # ((cmd > '/dev/null') ^ 'errors.txt') | (cmd > 'output.txt')
    assert type(expr) is Pipe
    lhs, rhs = expr.lhs, expr.rhs
    assert type(lhs) is Piperr
    assert type(lhs.lhs) is Redirect
    assert lhs.lhs.rhs == '/dev/null'
    assert lhs.rhs == 'errors.txt'
    assert type(rhs) is Redirect
    assert rhs.rhs == 'output.txt'


def test_multiline():
    #TODO: this should be a TokenIO test
    code = lex('( cmd\n    >       \nfname\n)')
    assert code == '( cmd\n    ^__PYSH_GT__&       \nfname\n)'

@pytest.mark.skip('TokenIO doesn\'t handle continuations???!!!!')
def test_continuation():
    #TODO: this should be a TokenIO test
    code = lex('cmd \\\n>\\\nfname')
    assert code == 'cmd \n^__PYSH_GT__&\nfname'


