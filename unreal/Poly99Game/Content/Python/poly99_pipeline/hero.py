"""Create/update the poly99+ hero MetaHuman and assemble it for gameplay.

Run in the editor (via Poly99Toolset.run_python):
    from poly99_pipeline import hero; hero.build()

Steps: create MetaHumanCharacter -> body/skin/eyes -> auto-rig (cloud) ->
texture sources (cloud) -> assemble (Optimized pipeline) -> save.
"""

from __future__ import annotations

import unreal

from metahuman_toolset.metahuman import MetaHumanToolset, BodyShape, SkinTone, EyeColor

CHARACTER_PATH = "/Game/Characters/Hero/MHC_Hero"

# Default hero. Other presets (loadout menu) reuse build() with different values.
DEFAULT = {
    "body": {"masculine_feminine": 0.25, "fat": 0.15, "muscularity": 0.75, "height_cm": 182.0},
    "skin": {"redness": 0.45, "lightness": 0.4},
    "eyes": {"brightness": 0.35, "temperature": 0.7},
}

_SUB = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)


def _object_path(asset_path: str) -> str:
    return "{0}.{1}".format(asset_path, asset_path.rsplit("/", 1)[-1])


def _apply_look(session, look: dict) -> None:
    body = BodyShape()
    for k, v in look["body"].items():
        setattr(body, k, v)
    MetaHumanToolset.set_body_shape(session, body)

    skin = SkinTone()
    for k, v in look["skin"].items():
        setattr(skin, k, v)
    MetaHumanToolset.set_skin_tone(session, skin)

    eyes = EyeColor()
    for k, v in look["eyes"].items():
        setattr(eyes, k, v)
    MetaHumanToolset.set_eye_color(session, eyes)


def build(asset_path: str = CHARACTER_PATH, look: dict | None = None, rig: bool = True,
          textures: bool = True, assemble: bool = True,
          quality=unreal.MetaHumanQualityLevel.MEDIUM) -> str:
    look = look or DEFAULT
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        MetaHumanToolset.create(asset_path)
        unreal.log("[poly99] created " + asset_path)

    session = MetaHumanToolset.begin_edit(_object_path(asset_path))
    character = session.character
    report = []
    try:
        _apply_look(session, look)
        report.append("look applied")

        if rig:
            p = unreal.MetaHumanCharacterAutoRiggingRequestParams()
            p.set_editor_property("rig_type", unreal.MetaHumanRigType.JOINTS_ONLY)
            p.set_editor_property("blocking", True)
            p.set_editor_property("report_progress", True)
            _SUB.request_auto_rigging(character, p)
            report.append("auto-rig requested (blocking)")

        if textures:
            t = unreal.MetaHumanCharacterTextureRequestParams()
            t.set_editor_property("blocking", True)
            t.set_editor_property("report_progress", True)
            _SUB.request_texture_sources(character, t)
            report.append("texture sources requested (blocking)")

        unreal.EditorAssetLibrary.save_loaded_asset(character, only_if_is_dirty=False)
        report.append("character saved")

        if assemble:
            if not _SUB.can_build_meta_human(character, True):
                report.append("NOT BUILDABLE (see log: likely rig/textures missing)")
            else:
                params = unreal.MetaHumanCharacterEditorBuildParameters()
                params.set_editor_property("pipeline_type", unreal.MetaHumanDefaultPipelineType.OPTIMIZED)
                params.set_editor_property("pipeline_quality", quality)
                _SUB.build_meta_human(character, params)
                report.append("assembled (Optimized, {})".format(quality))
    finally:
        MetaHumanToolset.end_edit(session)
        unreal.EditorAssetLibrary.save_directory("/Game/", only_if_is_dirty=True, recursive=True)

    return "; ".join(report)
