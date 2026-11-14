# Page layout

**Agreed 2026-11-13 (TF01.1).** The reference is the mockup in `mockup/`
(`index.html` + `data.js`, built by `make_mockup_data.py` from the `viz01`
drive). It is also published as a private artifact:
https://claude.ai/artifact/H16mhXiNCF5SCbWkBYuQQH. TF01.7 and TF01.8 start
from it.

No screenshot is saved: the mockup was built on the robot, which has no
browser. The mockup itself is the picture; open it to see the layout.

## Arrangement

- **Top bar**: name and map name on the left, **one status line** on the
  right.
- **The map fills the rest**, with a **sidebar on the right** (about
  320 px). Below 760 px wide, the sidebar gives way to floating panels.
- **Sidebar, top to bottom**: the camera, then the objects list.
- **Map controls, bottom left**: the scale bar, then zoom + and −, Fit
  map, Follow robot, and Laser (shows or hides the scan).

## Map

- **Floor**: the area SLAM has seen, as one light fill with slightly
  softened edges. Unknown space is the page background.
- **Walls**: **straight segments**, fitted to the wall cells along the
  room's own direction, with corners closed and doorways left open. Wall
  cells that fit no line are small grey marks. Not cell-by-cell, and not
  blurred.
- **Coordinate grid**: faint lines in the `map` frame every 0.5, 1, 2, 5 or
  10 m depending on zoom, labelled in metres on the top and left edges. The
  x = 0 and y = 0 axes are stronger, in neutral grey (not red and green).
  The origin is a marked dot labelled **0, 0**, with x pointing right and y
  pointing up.
- **Robot**: top view of DOME, to scale from `dome2`'s URDF: 0.30 m round
  plate, drive wheels, caster, lidar puck, camera bar at the front, and a
  heading chevron. It never shrinks below about 30 px. Grey with no halo
  when the robot isn't connected.
- **Trail**: a soft line in the robot colour, older parts fainter.
- **Laser**: the latest scan as faint rays from the lidar to each hit, plus
  a dot at each hit. Hidden when the robot isn't connected.

## Objects

- **On the map**: a coloured pin plus a chip with the class icon and short
  ID (`CN5`, `CP17`). The selected object's chip adds the display name
  ("CN5 · soda can"). Where chips would overlap, only the pin shows.
- **Lost objects** (not seen for more than 5 s): faded, with a dashed
  outline. Never hidden.
- **Objects list** in the sidebar: "In view now" first, then "Seen
  earlier", each row with the icon, ID, display name, and when it was last
  seen. Selecting an object shows its details (status, last seen,
  position, sightings).
- **Selecting** an object, on the map or in the list, never changes the
  zoom. The map pans smoothly only if the object is off-screen or behind a
  panel. Click it again, or click empty map, to deselect.

## Camera

- **Off by default.** The panel says turning it on adds load on the robot.
  A switch turns it on (the bridge subscribes) and off (it unsubscribes).

## Status

- **One plain sentence** with a coloured dot: "Live · map updated 1 s ago"
  (green), "Waiting for the map · robot connected" (amber), "Robot not
  connected · last heard 2 min ago" (red).
- **Clicking it** opens a small panel with when each source was last heard
  from: Map, Robot, Objects, Laser, Camera.
- **Robot not connected** also puts a banner over the map ("Showing the last
  map, from 2 min ago") and dims the map. **No map yet** shows a waiting
  screen in place of the map.

## Look

- **Theme follows the system setting**, light or dark. Both are designed.
- **Type**: Archivo for the interface, IBM Plex Mono for IDs, numbers and
  coordinates.
- **Colours**: robot teal, can rust, cup violet; green, amber and red only
  for status.
