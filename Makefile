lint:
	pylint --rcfile pylint.rc ./synthetick
	pylint --rcfile pylint.rc ./tests
reverse:
	pyreverse -o png ./synthetick/

