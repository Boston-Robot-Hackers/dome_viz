# Notes

Semi-permanent project notes: durable architecture decisions that don't belong
in a feature or task file.

## Keep the Pi's load unchanged

**Decided 2026-11-13.** A web page served from the Pi was rejected because it
adds load to a Pi that has none to spare (`dome_vision` I02, `dome_semantic`
TF33.9). Everything runs on the laptop.

**How to apply**: anything optional that costs the Pi, such as the camera
image, is subscribed only while the user is looking at it. `dome_vision` only
publishes images when someone subscribes, so an unsubscribed topic costs the Pi
nothing.

## Bags for replay need `/map` and the image

The `dome_semantic` F36 bags (e.g. `~/bags/f36run6`) record `/tf`,
`/tf_static`, `/oak/detections_3d`, `/odom`, `/scan` and `/semantic/targets`,
but **not `/map` or the camera image**. For replay, either record new bags
with `/map` and `/oak/image_annotated_compressed` added, or run `slam_toolbox`
on the laptop against the bag's `/scan`.
