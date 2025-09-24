lint:
	pylint --rcfile pylint.rc ./synthetick
	pylint --rcfile pylint.rc ./tests
	flake8 ./synthetick
	flake8 ./tests
reverse:
	pyreverse -o png ./synthetick/

test-dataset:
	coverage run -m pytest -k test_dataset

build:
	rm -f ./dist/*
	python -m build
	twine upload ./dist/*