"""Verify both archive layouts and restricted registration from extracted code."""
import importlib.util
from pathlib import Path
import runpy
import sys
import tempfile
import types
import zipfile
import bpy
try:
    from _bpy_restrict_state import RestrictBlend
except ImportError:
    from bpy_restrict_state import RestrictBlend

root = Path(__file__).resolve().parents[1]
runpy.run_path(str(root / 'tools' / 'build.py'))
for legacy in (True, False):
    archive = root / 'dist' / ('quick_cloth-1.1.0-legacy.zip' if legacy else 'quick_cloth-1.1.0.zip')
    with tempfile.TemporaryDirectory(prefix='qc_package_') as tmp:
        folder = Path(tmp)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            assert not any('/tests/' in name or name.startswith(('tests/', 'audit/', 'requirements/')) for name in z.namelist())
            z.extractall(folder)
        if legacy:
            folder /= 'quick_cloth'
            name = 'qc_legacy_package'
        else:
            name = 'bl_ext.qc_test.quick_cloth'
            for namespace in ('bl_ext', 'bl_ext.qc_test'):
                module = types.ModuleType(namespace)
                module.__path__ = [str(folder)]
                sys.modules[namespace] = module
        spec = importlib.util.spec_from_file_location(name, folder / '__init__.py', submodule_search_locations=[str(folder)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        with RestrictBlend():
            spec.loader.exec_module(module)
            module.register()
        assert hasattr(bpy.types.Object, 'quick_cloth')
        module.unregister()
        for key in list(sys.modules):
            if key == name or key.startswith(name + '.'):
                del sys.modules[key]
print('QC_TEST PASS extension and legacy archive registration')
