PROJECT_NAME = movement_primitives
DATE    ?= $(shell date +%FT%T%z)

PYTHON = python

.PHONY: deps
deps: $(info $(M) get the dependencies...)
	python -m pip install --upgrade pip
	pip install -r requirements.txt


.PHONY: lint
lint: $(info $(M) linting check of package...)
	pip install -e .  > /dev/null && pip install flake8 > /dev/null && pip install black > /dev/null
	black src/$(PROJECT_NAME)

.PHONY: run
run: $(info $(M) run car racing...)
	python src/movement_primitives/car_racing.py $(crn) $(ctrl)