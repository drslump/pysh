docs:
	@ $(MAKE) -C docs apidoc html
	@ echo file://$(PWD)/docs/_build/html/index.html

gh-pages: docs
# Assumes that docs/gh-pages is a git submodule pointing to the gh-pages
# branch of this repository:
#
#	> git submodule add -b gh-pages git@github.com/drslump/pysh docs/gh-pages
#
# That branch is totally clean (no project files), just with a .nojekyll
# file to signal GH we don't want Jekyll for our pages.
#
# Then we just copy the locally generated docs to that submodule and push
# to github.
#
	@ rm -rf docs/gh-pages/*
	@ cp -r docs/_build/html/* docs/gh-pages/
	@ cd docs/gh-pages ; \
	  	git add * ; \
	  	git commit -m "make gh-pages" ; \
	  	git push origin gh-pages

version-%:
	@ sed -i '' "s/r'[^']*'/r'$*'/" pysh/version.py
	@ cat pysh/version.py | grep __version__

.PHONY: docs
