import unreal

from poly99_toolset.toolset import Poly99Toolset

unreal.ToolsetRegistry.register_toolset_class(Poly99Toolset)
unreal.log("[poly99] Poly99Toolset registered")
