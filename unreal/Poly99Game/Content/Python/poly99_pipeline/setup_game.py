"""Create the gameplay assets that wire C++ classes to content (idempotent).

    from poly99_pipeline import setup_game; setup_game.run()

- /Game/Poly99/Data/DA_Hero_Default   UPoly99HeroLoadout -> BP_MHC_Hero
- /Game/Poly99/Blueprints/BP_Poly99Hero      (APoly99HeroPawn, Loadout set)
- /Game/Poly99/Blueprints/BP_Poly99GameMode  (APoly99GameMode, pawn = BP_Poly99Hero)
- /Game/Poly99/Maps/L_Arena                  test arena; set as editor/game default map
"""

from __future__ import annotations

import unreal

HERO_BP_CLASS = "/Game/Characters/Hero/Unpacked/MHC_Hero/BP_MHC_Hero.BP_MHC_Hero_C"
DATA = "/Game/Poly99/Data"
BPS = "/Game/Poly99/Blueprints"
MAP = "/Game/Poly99/Maps/L_Arena"

_assets = unreal.AssetToolsHelpers.get_asset_tools()
_lib = unreal.EditorAssetLibrary


def _load_or_create(path: str, cls, factory=None):
    if _lib.does_asset_exist(path):
        return unreal.load_asset(path)
    folder, name = path.rsplit("/", 1)
    return _assets.create_asset(name, folder, cls, factory)


def _blueprint(path: str, parent: unreal.Class) -> unreal.Blueprint:
    if _lib.does_asset_exist(path):
        return unreal.load_asset(path)
    f = unreal.BlueprintFactory()
    f.set_editor_property("parent_class", parent)
    folder, name = path.rsplit("/", 1)
    return _assets.create_asset(name, folder, None, f)


def _cdo(bp: unreal.Blueprint):
    return unreal.get_default_object(unreal.load_object(None, bp.generated_class().get_path_name()))


def make_loadout() -> unreal.Object:
    da = _load_or_create(DATA + "/DA_Hero_Default", unreal.Poly99HeroLoadout, unreal.DataAssetFactory())
    da.set_editor_property("meta_human_class", unreal.load_object(None, HERO_BP_CLASS))
    _lib.save_loaded_asset(da)
    return da


def make_blueprints(loadout) -> tuple:
    hero = _blueprint(BPS + "/BP_Poly99Hero", unreal.Poly99HeroPawn)
    _cdo(hero).set_editor_property("loadout", loadout)
    unreal.BlueprintEditorLibrary.compile_blueprint(hero)
    _lib.save_loaded_asset(hero)

    gm = _blueprint(BPS + "/BP_Poly99GameMode", unreal.Poly99GameMode)
    _cdo(gm).set_editor_property("default_pawn_class", hero.generated_class())
    unreal.BlueprintEditorLibrary.compile_blueprint(gm)
    _lib.save_loaded_asset(gm)
    return hero, gm


def make_map(gm) -> None:
    """L_Arena: sun + sky atmosphere + realtime sky light + fog (engine defaults, no exposure override) + arena."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not _lib.does_asset_exist(MAP):
        les.new_level(MAP)
    les.load_level(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in actors.get_all_level_actors():
        if a.get_actor_label().startswith("poly99_"):
            actors.destroy_actor(a)

    def spawn(cls, label, loc=(0, 0, 0), rot=(0, 0, 0)):
        a = actors.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(*rot))
        a.set_actor_label(label)
        return a

    sun = spawn(unreal.DirectionalLight, "poly99_Sun", (0, 0, 1000), (0, -50, 35))
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    sun.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    spawn(unreal.SkyAtmosphere, "poly99_Atmosphere")
    sky = spawn(unreal.SkyLight, "poly99_SkyLight", (0, 0, 800))
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property("real_time_capture", True)
    spawn(unreal.ExponentialHeightFog, "poly99_Fog", (0, 0, -200))
    spawn(unreal.PlayerStart, "poly99_PlayerStart", (0, 0, 100))

    # Arena bounds marker: core arena 1280x720 units * 2 UU = 2560 (Y) x 1440 (X) UU.
    floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 1), unreal.Rotator(0, 0, 0))
    floor.set_actor_label("poly99_ArenaFloor")
    floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Plane"))
    floor.set_actor_scale3d(unreal.Vector(14.4, 25.6, 1.0))

    ws = unreal.EditorLevelLibrary.get_editor_world().get_world_settings()
    ws.set_editor_property("default_game_mode", gm.generated_class())
    les.save_current_level()
    # Default maps live in Config/DefaultEngine.ini ([/Script/EngineSettings.GameMapsSettings]).


def run() -> str:
    loadout = make_loadout()
    hero, gm = make_blueprints(loadout)
    make_map(gm)
    return "ok: loadout, BP_Poly99Hero, BP_Poly99GameMode, L_Arena"
