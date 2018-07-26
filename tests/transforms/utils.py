from io import StringIO
from textwrap import dedent
from functools import partial

from pysh.transforms import Compiler


def lex(modules, code):
    comp = Compiler(modules)
    return comp.lex(StringIO(dedent(code))).read()

def parse(modules, code):
    comp = Compiler(modules)
    return comp.parse(StringIO(dedent(code)))

def comp(modules, code):
    comp = Compiler(modules)
    return comp.compile(StringIO(dedent(code)))

def auto(modules, code):
    comp = Compiler(list(modules) + ['autoreturn'])
    func = comp.compile(dedent(code))
    return func()

def factory(*modules):
    return partial(lex, modules), partial(parse, modules), \
           partial(comp, modules), partial(auto, modules)
