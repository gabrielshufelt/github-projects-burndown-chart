instructions:
	@echo "[NOTE]: If you see any errors, make sure your virtual environment is active!"

build: instructions
	pip install -r requirements.txt


run: instructions
ifeq ($(OS),Windows_NT)
	cd ./src/github_projects_burndown_chart && set PYTHONPATH=. && python main.py $(type) $(name) $(opts)
else
	cd ./src/github_projects_burndown_chart && PYTHONPATH=. python main.py $(type) $(name) $(opts)
endif

test: instructions
	coverage run \
		--source=src/github_projects_burndown_chart \
		--branch \
		-m unittest discover -v

.PHONY: build run test