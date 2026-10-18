import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking

with tempfile.TemporaryDirectory(prefix='qc_storage_') as temporary:
    obj = mesh('DiskGarment')
    p = addon.initialize_setup(obj, bpy.context.scene)
    p.frame_end = 3
    p.use_disk_cache = True
    filename = str(Path(temporary) / 'cloth.blend')
    bpy.ops.wm.save_as_mainfile(filepath=filename)
    assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
    assert bpy.ops.quick_cloth.bake() == {'FINISHED'}
    assert list(Path(temporary).rglob('*.bphys')), 'No native disk cache files produced'
    bpy.ops.wm.save_as_mainfile(filepath=filename)
    bpy.ops.wm.open_mainfile(filepath=filename)
    obj = bpy.data.objects['DiskGarment']
    p = obj.quick_cloth
    assert p.bake_needs_validation
    assert addon.find_cloth_modifier(obj).point_cache.is_baked
    p.mass += .01
    assert baking.state(bpy.context, obj) == 'DIRTY'
print('QC_TEST PASS disk cache save and reopen')
