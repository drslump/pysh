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
# Also note that docs/gh-pages should be ignored, adding `ignore = dirty` on
# its section in the .gitmodules file. This avoids having to track its changes.
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

	@ echo "Last commits for the release notes"
	@ git log -15 --pretty=format:"- %s"

dev:
	pip install -e .[dev]

builder:
	pip install --upgrade pip setuptools wheel twine
	pip install -e .[dev,build]
	wget --content-on-error -q -O docs/plantuml.jar http://sourceforge.net/projects/plantuml/files/plantuml.jar

travis: builder
	pytest

test:
	pytest

.PHONY: docs gh-pages test travis dev builder
