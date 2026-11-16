# Makefile — commands for using dome_viz
#
# Only tool targets live here: what a user of the app runs. Development
# commands (build, tests, ruff) are in CLAUDE.md's Commands section.
#
# view and replay differ in their clock, and mixing them up fails silently
# (no robot drawn): the live robot needs wall time, a bag needs sim time.

.PHONY: help

.DEFAULT_GOAL := help

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} \
		/^[a-zA-Z_-]+:.*## / {printf "  %-8s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: view replay stop

view: ## LIVE ROBOT only, on wall time. For a bag use make replay
	@if ros2 topic list 2>/dev/null | grep -qx /clock; then \
		echo "Something is publishing /clock (a bag replay?)."; \
		echo "make view is for the live robot. Use: make stop; make replay BAG=<bag>"; \
		exit 1; fi
	bl dome_viz view.launch.py

# The bracketed first letters stop pkill matching the shell that runs it,
# which otherwise kills this recipe mid-way.
stop: ## Stop the viewer and any bag replay, and free the port
	@pkill -f "[l]ib/dome_viz/bridge_node" || true
	@pkill -f "[v]iew.launch.py" || true
	@pkill -f "[r]os2 bag play" || true
	@sleep 1
	@ss -ltn | grep -q ":8080" && echo "WARNING: 8080 still held" || echo "stopped; 8080 free"

replay: ## BAG REPLAY, on sim time: make replay BAG=~/.dome/bags/viz01
	@test -n "$(BAG)" || { echo "Say which bag: make replay BAG=~/.dome/bags/viz01"; exit 1; }
	@test -e "$(BAG)" || { echo "No bag at $(BAG)"; exit 1; }
	@if pgrep -f "[l]ib/dome_viz/bridge_node" >/dev/null || pgrep -f "[r]os2 bag play" >/dev/null; then \
		echo "A viewer or a bag is already running; two at once confuse the clock (I02)."; \
		echo "Run make stop first."; exit 1; fi
	@echo "Replaying $(BAG) on sim time. Ctrl+C stops both."
	bl dome_viz view.launch.py --sim_time True & \
	sleep 4 && ros2 bag play $(BAG) --clock; kill %1
