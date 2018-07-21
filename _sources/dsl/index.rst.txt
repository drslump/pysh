Domain Specific Language
========================

One of the core goals of *pysh* is to be ergonomic so it's pleasant to write
shell scripts with it. However there is a fine line between optimizing a syntax
for a use case and creating a whole new language with its own set of quirks.

With that premise the domain specific language tries to have a limited scope,
exposing as few symbols and operators as possible, where the ones used shall
not be confusing or erratic, following the *principle of least astonishment*.

.. Important::
    In other words, if a Python programmer cannot figure out what a *pysh*
    script does just by glancing at a *cheatsheet*, then we have failed to meet
    our goal.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   types
   operators
