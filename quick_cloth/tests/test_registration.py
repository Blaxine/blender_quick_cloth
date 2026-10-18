"""blender --background --factory-startup --python-exit-code 1 --python tests/test_registration.py"""
import importlib.util
from pathlib import Path
import bpy
from _bpy_restrict_state import RestrictBlend

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quick_cloth', root / '__init__.py', submodule_search_locations=[str(root)])
addon = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
for _ in range(2):
    with RestrictBlend():
        addon.register()
    ids = [c.bl_idname for c in addon.classes if issubclass(c, bpy.types.Operator)]
    assert len(ids) == len(set(ids))
    assert 'quick_cloth.make_colliders' in ids
    assert 'quick_cloth.pin_from_rig_weights' in ids
    addon.unregister()
    addon.unregister()
print('QC_TEST PASS registration')
