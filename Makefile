lint:
	pylint --rcfile pylint.rc ./synthetick
	pylint --rcfile pylint.rc ./tests
	flake8 ./synthetick
	flake8 ./tests
reverse:
	pyreverse -o png ./synthetick/

