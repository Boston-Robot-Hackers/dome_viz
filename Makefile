# Makefile — commands for using dome_viz
#
# Only tool targets live here: what a user of the app runs. Development
# commands (sync, tests, ruff) run through `uv` directly; see CLAUDE.md.

.PHONY: help

.DEFAULT_GOAL := help

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} \
		/^[a-zA-Z_-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: view replay stop

view: ## Open the live map view (prints the URLs to open)
	bl dome_viz view.launch.py

# The bracketed first letters stop pkill matching the shell that runs it,
# which otherwise kills this recipe mid-way.
stop: ## Stop the viewer and any bag replay, and free the port
	@pkill -f "[l]ib/dome_viz/bridge_node" || true
	@pkill -f "[v]iew.launch.py" || true
	@pkill -f "[r]os2 bag play" || true
	@sleep 1
	@ss -ltn | grep -q ":8080" && echo "WARNING: 8080 still held" || echo "stopped; 8080 free"

replay: ## Open the view against a recorded bag: make replay BAG=~/.dome/bags/viz01
	bl dome_viz view.launch.py --sim_time True & \
	sleep 4 && ros2 bag play $(BAG) --clock; kill %1
