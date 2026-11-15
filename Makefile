# Makefile — commands for using dome_viz
#
# Only tool targets live here: what a user of the app runs. Development
# commands (sync, tests, ruff) run through `uv` directly; see CLAUDE.md.

.PHONY: help

.DEFAULT_GOAL := help

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} \
		/^[a-zA-Z_-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: view replay

view: ## Open the live map view (prints the URLs to open)
	bl dome_viz view.launch.py

replay: ## Open the view against a recorded bag: make replay BAG=~/.dome/bags/viz01
	bl dome_viz view.launch.py --use_sim_time True & \
	sleep 4 && ros2 bag play $(BAG) --clock; kill %1
