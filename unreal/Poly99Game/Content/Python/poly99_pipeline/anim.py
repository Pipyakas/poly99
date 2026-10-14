"""Hero locomotion blend space from the MetaHuman UEFN locomotion preset.

    from poly99_pipeline import anim; anim.build()

BS_Hero_Locomotion: X = move direction relative to facing (deg, -180..180),
Y = planar speed (UU/s, 0..600). Twin-stick: the hero faces the aim while moving
in any direction, so F/B/L/R loops are all needed.
"""

from __future__ import annotations

import unreal

SRC = "/MetaHumanCharacter/Optional/Animation/UEFNAnimPreset/Locomotion/AS_MH_Neutral_"
DEST = "/Game/Poly99/Animation/BS_Hero_Locomotion"
SKELETON = "/MetaHumanCharacter/Female/Medium/NormalWeight/Body/metahuman_base_skel"

WALK, RUN = 180.0, 600.0
# (anim suffix, direction deg, speed). LR = moving right (left foot leads), RL = moving left.
SAMPLES = [
    ("Stand_Idle_Loop", -180.0, 0.0), ("Stand_Idle_Loop", -90.0, 0.0), ("Stand_Idle_Loop", 0.0, 0.0),
    ("Stand_Idle_Loop", 90.0, 0.0), ("Stand_Idle_Loop", 180.0, 0.0),
    ("Walk_Loop_F", 0.0, WALK), ("Walk_Loop_LR", 90.0, WALK), ("Walk_Loop_RL", -90.0, WALK),
    ("Walk_Loop_B", 180.0, WALK), ("Walk_Loop_B", -180.0, WALK),
    ("Run_Loop_F", 0.0, RUN), ("Run_Loop_LR", 90.0, RUN), ("Run_Loop_RL", -90.0, RUN),
    ("Run_Loop_B", 180.0, RUN), ("Run_Loop_B", -180.0, RUN),
]


def _axis(name: str, lo: float, hi: float, divisions: int) -> unreal.BlendParameter:
    p = unreal.BlendParameter()
    p.set_editor_property("display_name", name)
    p.set_editor_property("min", lo)
    p.set_editor_property("max", hi)
    p.set_editor_property("grid_num", divisions)
    return p


def build() -> str:
    lib = unreal.EditorAssetLibrary
    if lib.does_asset_exist(DEST):
        bs = unreal.load_asset(DEST)  # reuse: deleting a referenced asset stalls the editor
    else:
        f = unreal.BlendSpaceFactoryNew()
        f.set_editor_property("target_skeleton", unreal.load_asset(SKELETON))
        folder, name = DEST.rsplit("/", 1)
        bs = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.BlendSpace, f)

    bs.set_editor_property("blend_parameters", [_axis("Direction", -180.0, 180.0, 4), _axis("Speed", 0.0, RUN, 4), _axis("None", 0.0, 0.0, 0)])
    anims = [unreal.load_asset(SRC + suffix) for suffix, _, _ in SAMPLES]
    values = [unreal.Vector(direction, speed, 0.0) for _, direction, speed in SAMPLES]
    added = unreal.Poly99EditorUtils.build_blend_space(bs, anims, values)
    if added != len(SAMPLES):
        unreal.log_warning("[poly99] blend space accepted {}/{} samples".format(added, len(SAMPLES)))
    lib.save_loaded_asset(bs)
    return "{}/{} samples -> {} (length {:.2f}s)".format(added, len(SAMPLES), DEST, bs.get_play_length())
