import math

import numpy as np
import pytest

from termin.geombase import GeneralPose3, Mat33, Mat33f, Pose3, Vec3, Vec3f


def assert_vec3_close(actual: Vec3, expected: tuple[float, float, float], eps: float = 1e-6) -> None:
    assert actual.x == pytest.approx(expected[0], abs=eps)
    assert actual.y == pytest.approx(expected[1], abs=eps)
    assert actual.z == pytest.approx(expected[2], abs=eps)


def test_mat33_rotation_z_uses_column_major_storage_and_row_major_rows() -> None:
    mat = Mat33.rotation_z(math.pi / 2)

    transformed = mat.transform(Vec3(1.0, 0.0, 0.0))
    assert_vec3_close(transformed, (0.0, 1.0, 0.0))

    rows = np.asarray(mat.to_rows())
    np.testing.assert_allclose(
        rows,
        np.array(
            [
                [0.0, -1.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        ),
        atol=1e-6,
    )

    assert mat[1, 0] == pytest.approx(-1.0, abs=1e-6)


def test_pose3_rotation_mat33_matches_legacy_row_major_matrix() -> None:
    pose = Pose3.rotateZ(math.pi / 2)

    legacy_rows = np.asarray(pose.rotation_matrix())
    mat_rows = np.asarray(pose.rotation_mat33().to_rows())

    np.testing.assert_allclose(mat_rows, legacy_rows, atol=1e-6)
    assert_vec3_close(pose.rotation_mat33() @ Vec3(1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def test_general_pose3_rotation_mat33_matches_legacy_row_major_matrix() -> None:
    pose = GeneralPose3.rotateZ(math.pi / 2)

    legacy_rows = np.asarray(pose.rotation_matrix())
    mat_rows = np.asarray(pose.rotation_mat33().to_rows())

    np.testing.assert_allclose(mat_rows, legacy_rows, atol=1e-6)


def test_mat33f_transform_and_float_conversion() -> None:
    mat = Mat33.rotation_z(math.pi / 2).to_float()
    assert isinstance(mat, Mat33f)

    transformed = mat @ Vec3f(1.0, 0.0, 0.0)
    assert transformed.x == pytest.approx(0.0, abs=1e-6)
    assert transformed.y == pytest.approx(1.0, abs=1e-6)
    assert transformed.z == pytest.approx(0.0, abs=1e-6)
