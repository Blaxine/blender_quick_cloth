"""Quality affects numerical fidelity, never fabric or collision policy."""

# Fixed (solver steps, collision steps) per tier; the same for every fabric.
TIERS = {'PREVIEW': (20, 3), 'LOW': (32, 4), 'MEDIUM': (64, 5), 'HIGH': (120, 8)}
_syncing = set()


def resolve(props):
    return TIERS.get(props.quality_mode, (props.quality_steps, props.collision_quality))


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
