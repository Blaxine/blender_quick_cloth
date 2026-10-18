"""Quality affects numerical fidelity, never fabric or collision policy."""
from math import ceil

FABRIC_STEPS = {'SIMPLE': 5, 'COTTON': 8, 'POLYESTER': 10, 'COUCH_LEATHER': 15,
                'LEATHER_COAT': 12, 'LATEX': 14, 'STRETCH_DENIM': 11,
                'RIGID_DENIM': 12, 'SELVEDGE_DENIM': 14}
_syncing = set()


def resolve(props):
    base = FABRIC_STEPS.get(props.preset, 12)
    if props.quality_mode == 'PREVIEW':
        return max(6, ceil(base / 2)), 3
    if props.quality_mode == 'MEDIUM':
        return max(12, base), 5
    if props.quality_mode == 'HIGH':
        return max(20, ceil(1.5 * base)), 8
    return props.quality_steps, props.collision_quality


def selection_update(props, context):
    ptr = props.as_pointer()
    if ptr in _syncing:
        return
    _syncing.add(ptr)
    try:
        if props.quality_mode == 'CUSTOM':
            props.quality_steps = props.custom_steps
            props.collision_quality = props.custom_collision
        else:
            props.quality_steps, props.collision_quality = resolve(props)
    finally:
        _syncing.remove(ptr)


def values_update(props, context):
    ptr = props.as_pointer()
    if ptr in _syncing:
        return
    _syncing.add(ptr)
    try:
        props.custom_steps = props.quality_steps
        props.custom_collision = props.collision_quality
        props.quality_mode = 'CUSTOM'
    finally:
        _syncing.remove(ptr)
