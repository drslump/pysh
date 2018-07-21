docs:
	@ $(MAKE) -C docs apidoc html
	@ echo file://$(PWD)/docs/_build/html/index.html

version-%:
	@ sed -i '' "s/r'[^']*'/r'$*'/" pysh/version.py
	@ cat pysh/version.py | grep __version__

.PHONY: docs
