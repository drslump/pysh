from pysh.command import command


def test_args_short():
    c = command('cmd')
    r = c(a=True, b=True, c=False, d=10)
    assert r.args == ['-a', '-b', '-d', '10']

def test_args_hyphenate():
    c = command('cmd')
    r = c('bar', opt_bool=True, opt_str='str', opt_multi=[1,2])
    assert  ' '.join(r.args) \
        == '--opt-bool --opt-multi 1 --opt-multi 2 --opt-str str bar'

def test_args_valuepre():
    c = command('cmd', valuepre='=')
    r = c(opt=1)
    assert ' '.join(r.args) == '--opt=1'
    r = c(opt=[1,2])
    assert ' '.join(r.args) == '--opt=1 --opt=2'

def test_args_argspre():
    c = command('cmd', argspre='--')
    r = c('bar', 'baz', opt=True)
    assert ' '.join(r.args) == '--opt -- bar baz'
    r = c('foo', 'bar')
    assert r.args == ['--', 'foo', 'bar']

def test_args_slice():
    c = command('cmd')
    assert c['foo'].args == ['foo']
    assert c['foo bar'].args == ['foo', 'bar']
    assert c[r'foo\ bar'].args == ['foo bar']
    assert c[r'foo\ \ bar'].args == ['foo  bar']
    assert c['foo\\\tbar'].args == ['foo\tbar']

def test_args_repeat():
    c = command('cmd', repeat=',')
    assert c(opt=[1,2,3]).args == ['--opt', '1,2,3']
    c = command('cmd', repeat=',', valuepre='=')
    assert c(opt=[1,2,3]).args == ['--opt=1,2,3']
