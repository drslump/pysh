Unreleased
----------

- Introduce the notion of *alpha*, *beta* and *deprecated* transform modules.
- :mod:`pysh.transforms.restring` transform ``re'...'``
- :mod:`pysh.transforms.pathstring` transform  ``_'...'``
- :mod:`pysh.transforms.pathpow` transform to allow ``**`` in paths
- :mod:`pysh.transforms.precedence` transform to fix operator binging
- Rudimentary quick help about symbols with ``pysh -h <symbol>``
- Travis CI setup
- Documentation now published at https://drslump.github.io/pysh/

Version 0.0.3
-------------

- Eval mode (``pysh -e 'code'``) working with :mod:`pysh.transforms.autoimport`
  and :mod:`pysh.transforms.autoreturn` transforms.

Version 0.0.1
-------------

- Nothing works, just a bunch of ideas in the readme
