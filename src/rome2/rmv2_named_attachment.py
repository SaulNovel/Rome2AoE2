"""RMV2 named-attachment matrix composition recovered from Rome II runtime."""

RMV_MODEL_FRAME = (
    (-1.0, 0.0, 0.0, 0.0),
    (0.0, -1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)


def multiply(left, right):
    """Multiply two 4x4 column-vector matrices without external dependencies."""
    return tuple(
        tuple(sum(left[row][k] * right[k][column] for k in range(4)) for column in range(4))
        for row in range(4)
    )


def affine_3x4(rows):
    if len(rows) != 3 or any(len(row) != 4 for row in rows):
        raise ValueError("an RMV2 named attachment must contain a 3x4 matrix")
    return tuple(tuple(float(value) for value in row) for row in rows) + ((0.0, 0.0, 0.0, 1.0),)


def named_attachment_local(serialized_rows):
    """Return RMV_MODEL_FRAME * the direct serialized named-attachment matrix."""
    return multiply(RMV_MODEL_FRAME, affine_3x4(serialized_rows))


def compose_runtime(root, animated_bone_delta, bone_world_bind, serialized_rows, child_pivot):
    """Reproduce Rome II's observed named rigid-child transform in exact order."""
    result = multiply(root, animated_bone_delta)
    result = multiply(result, bone_world_bind)
    result = multiply(result, RMV_MODEL_FRAME)
    result = multiply(result, affine_3x4(serialized_rows))
    return multiply(result, child_pivot)
