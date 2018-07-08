from pysh.command import Command


def test_hyphenate():
    c = Command('foo')
    r = c('bar', opt_bool=True, opt_str='str', opt_multi=[1,2])
    assert  ' '.join(r.args) \
        == '--opt-bool --opt-multi 1 --opt-multi 2 --opt-str str bar'

def test_valuepre():
    c = Command('foo', valuepre='=')
    r = c(opt=1)
    assert ' '.join(r.args) == '--opt=1'

def test_argspre():
    c = Command('foo', argspre='--')
    r = c('bar', 'baz', opt=True)
    assert ' '.join(r.args) == '--opt -- bar baz'

def test_slice_one():
    c = Command('foo')
    assert c['foo'].args == ['foo']
    assert c['foo bar'].args == ['foo', 'bar']
    assert c[r'foo\ bar'].args == ['foo bar']
    assert c['foo\\\tbar'].args == ['foo\tbar']
