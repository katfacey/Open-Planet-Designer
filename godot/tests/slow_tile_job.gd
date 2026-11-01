# SPDX-License-Identifier: GPL-3.0-or-later
extends "res://scripts/streaming/tile_job.gd"
## Fault-injection fixture: real requested tiles finish after camera demand changes.
func generate() -> Dictionary:
	OS.delay_msec(150)
	return super.generate()
