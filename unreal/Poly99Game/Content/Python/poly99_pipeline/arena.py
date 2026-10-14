"""Dress L_Arena with the Blender arena kit + neon lighting (idempotent).

    from poly99_pipeline import arena; arena.run()

Core arena is 1280 x 720 core units * 2 UU = 2560 (Y) x 1440 (X) UU, centred on the origin.
Floor tiles (400 cm) cover it with a one-tile margin; walls ring the margin; pillars sit on the
corners; glow strips trace the playable edge. Night lighting: dim moon + sky, neon point lights
(MegaLights) along the walls, emissive trims feed Lumen GI. Everything is labelled poly99_Kit_*.
"""

from __future__ import annotations

import unreal

from . import setup_game

KIT = "/Game/Poly99/Kit"
HALF_X, HALF_Y = 720.0, 1280.0
TILE = 400.0
WALL_X, WALL_Y = 1000.0, 1600.0  # wall line: one tile outside the playable area (multiples of 200)
PREFIX = "poly99_Kit_"
NEON = [unreal.LinearColor(0.0, 0.6, 1.0), unreal.LinearColor(1.0, 0.1, 0.6)]

_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _mesh(name: str, label: str, loc, yaw: float = 0.0):
    a = _actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*loc), unreal.Rotator(0, 0, yaw))
    a.set_actor_label(label)
    a.static_mesh_component.set_static_mesh(unreal.load_asset(f"{KIT}/{name}"))
    a.set_folder_path("Arena")
    return a


def _clear() -> None:
    for a in _actors.get_all_level_actors():
        label = a.get_actor_label()
        if label.startswith(PREFIX) or label == "poly99_ArenaFloor":
            _actors.destroy_actor(a)


def build_geometry() -> None:
    # Floor: tile centres on a 400 grid covering [-WALL, WALL]; tile top at z=0 (pivot at base, so z=-10).
    nx, ny = int(2 * WALL_X / TILE), int(2 * WALL_Y / TILE)
    for i in range(nx):
        for j in range(ny):
            x = -WALL_X + TILE * (i + 0.5)
            y = -WALL_Y + TILE * (j + 0.5)
            _mesh("SM_Floor_Tile_400", f"{PREFIX}Floor_{i}_{j}", (x, y, -10.0))

    # Walls: 400-long segments (along mesh X) on the long sides (Y = +-WALL_Y) and short sides.
    for i in range(nx):
        x = -WALL_X + TILE * (i + 0.5)
        _mesh("SM_Wall_400", f"{PREFIX}WallN_{i}", (x, WALL_Y, 0.0), 0.0)
        _mesh("SM_Wall_400", f"{PREFIX}WallS_{i}", (x, -WALL_Y, 0.0), 180.0)
    for j in range(ny):
        y = -WALL_Y + TILE * (j + 0.5)
        _mesh("SM_Wall_400", f"{PREFIX}WallE_{j}", (WALL_X, y, 0.0), 90.0)
        _mesh("SM_Wall_400", f"{PREFIX}WallW_{j}", (-WALL_X, y, 0.0), -90.0)

    for k, (sx, sy) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
        _mesh("SM_Pillar", f"{PREFIX}Pillar_{k}", (sx * WALL_X, sy * WALL_Y, 0.0))

    # Glow strips on the playable edge (floor level), 400 cm each.
    for i in range(int(2 * HALF_X // TILE) + 1):
        x = -HALF_X + TILE * (i + 0.5)
        if x > HALF_X:
            break
        _mesh("SM_Edge_GlowStrip", f"{PREFIX}EdgeN_{i}", (x, HALF_Y, 0.0), 0.0)
        _mesh("SM_Edge_GlowStrip", f"{PREFIX}EdgeS_{i}", (x, -HALF_Y, 0.0), 0.0)
    for j in range(int(2 * HALF_Y // TILE) + 1):
        y = -HALF_Y + TILE * (j + 0.5)
        if y > HALF_Y:
            break
        _mesh("SM_Edge_GlowStrip", f"{PREFIX}EdgeE_{j}", (HALF_X, y, 0.0), 90.0)
        _mesh("SM_Edge_GlowStrip", f"{PREFIX}EdgeW_{j}", (-HALF_X, y, 0.0), 90.0)

    # Spawn gates set into the short walls' centres, facing inward.
    _mesh("SM_Spawn_Gate", f"{PREFIX}GateN", (0.0, WALL_Y - 30.0, 0.0), 0.0)
    _mesh("SM_Spawn_Gate", f"{PREFIX}GateS", (0.0, -WALL_Y + 30.0, 0.0), 180.0)


def build_lighting() -> None:
    for a in _actors.get_all_level_actors():
        label = a.get_actor_label()
        if label == "poly99_Sun":
            a.light_component.set_intensity(0.6)
            a.light_component.set_light_color(unreal.LinearColor(0.55, 0.65, 1.0))
        elif label == "poly99_SkyLight":
            a.light_component.set_intensity(0.25)
    # Neon point lights along the walls (MegaLights makes many shadowed lights affordable).
    k = 0
    for side, (x0, y0, dx, dy, n) in enumerate([
        (-WALL_X + 200, WALL_Y - 120, 400, 0, int(2 * WALL_X / TILE)),
        (-WALL_X + 200, -WALL_Y + 120, 400, 0, int(2 * WALL_X / TILE)),
        (WALL_X - 120, -WALL_Y + 400, 0, 800, int(2 * WALL_Y / 800)),
        (-WALL_X + 120, -WALL_Y + 400, 0, 800, int(2 * WALL_Y / 800)),
    ]):
        for i in range(n):
            loc = unreal.Vector(x0 + dx * i, y0 + dy * i, 180.0)
            light = _actors.spawn_actor_from_class(unreal.PointLight, loc, unreal.Rotator(0, 0, 0))
            light.set_actor_label(f"{PREFIX}Neon_{k}")
            light.set_folder_path("Arena/Lights")
            comp = light.point_light_component
            comp.set_mobility(unreal.ComponentMobility.MOVABLE)
            comp.set_intensity(400.0)  # lumens; exposure is fixed (no auto exposure), keep these low
            comp.set_attenuation_radius(900.0)
            comp.set_light_color(NEON[(i + side) % 2])
            k += 1

    # Overhead key lights on a 480 x 640 grid so the hero and enemies read against the dark floor.
    for i in range(4):
        for j in range(5):
            loc = unreal.Vector(-720.0 + i * 480.0, -1280.0 + j * 640.0, 700.0)
            light = _actors.spawn_actor_from_class(unreal.SpotLight, loc, unreal.Rotator(-90, 0, 0))
            light.set_actor_label(f"{PREFIX}Key_{i}_{j}")
            light.set_folder_path("Arena/Lights")
            comp = light.spot_light_component
            comp.set_mobility(unreal.ComponentMobility.MOVABLE)
            comp.set_intensity(1500.0)
            comp.set_attenuation_radius(1600.0)
            comp.set_inner_cone_angle(50.0)
            comp.set_outer_cone_angle(75.0)
            comp.set_light_color(unreal.LinearColor(0.75, 0.82, 1.0))


def run() -> str:
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    les.load_level(setup_game.MAP)
    _clear()
    build_geometry()
    build_lighting()
    les.save_current_level()
    n = sum(1 for a in _actors.get_all_level_actors() if a.get_actor_label().startswith(PREFIX))
    return f"ok: {n} arena actors"
