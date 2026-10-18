import importlib.util
import sys
from pathlib import Path
import bpy

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quick_cloth', root / '__init__.py', submodule_search_locations=[str(root)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()

def mesh(name='Garment'):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=5, y_subdivisions=5, size=2)
    obj = bpy.context.object
    obj.name = name
    return obj
