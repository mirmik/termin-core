"""Tests for GeneralPose3 - pose with scale."""

import math
import pytest

from termin.geombase import GeneralPose3, Pose3, Vec3, Quat


def assert_vec3_approx(actual: Vec3, expected: tuple, eps=1e-6):
    """Helper to assert Vec3 is approximately equal to expected tuple."""
    assert abs(actual.x - expected[0]) < eps, f"x: {actual.x} != {expected[0]}"
    assert abs(actual.y - expected[1]) < eps, f"y: {actual.y} != {expected[1]}"
    assert abs(actual.z - expected[2]) < eps, f"z: {actual.z} != {expected[2]}"


class TestGeneralPose3Basics:
    """Basic GeneralPose3 functionality."""

    def test_identity(self):
        gp = GeneralPose3.identity()
        assert_vec3_approx(gp.lin, (0, 0, 0))
        assert gp.ang.x == pytest.approx(0)
        assert gp.ang.y == pytest.approx(0)
        assert gp.ang.z == pytest.approx(0)
        assert gp.ang.w == pytest.approx(1)
        assert_vec3_approx(gp.scale, (1, 1, 1))

    def test_default_constructor(self):
        gp = GeneralPose3()
        assert_vec3_approx(gp.lin, (0, 0, 0))
        assert gp.ang.w == pytest.approx(1)
        assert_vec3_approx(gp.scale, (1, 1, 1))

    def test_constructor_with_scale(self):
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            ang=Quat(0, 0, 0, 1),
            scale=Vec3(2, 3, 4)
        )
        assert_vec3_approx(gp.lin, (1, 2, 3))
        assert_vec3_approx(gp.scale, (2, 3, 4))

    def test_copy(self):
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            scale=Vec3(2, 2, 2)
        )
        gp_copy = gp.copy()

        # Check copy has same values
        assert gp_copy.lin.x == pytest.approx(1)
        assert gp_copy.scale.x == pytest.approx(2)


class TestGeneralPose3Composition:
    """Test pose composition with scale."""

    def test_composition_identity(self):
        """Identity * pose = pose."""
        identity = GeneralPose3.identity()
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            scale=Vec3(2, 2, 2)
        )
        result = identity * gp
        assert_vec3_approx(result.lin, (1, 2, 3))
        assert_vec3_approx(result.scale, (2, 2, 2))

    def test_composition_scale_affects_child_position(self):
        """Parent scale affects child's global position."""
        parent = GeneralPose3(scale=Vec3(2, 2, 2))
        child = GeneralPose3(lin=Vec3(1, 0, 0))

        result = parent * child

        # Child at [1,0,0] with parent scale [2,2,2] -> global [2,0,0]
        assert_vec3_approx(result.lin, (2, 0, 0))

    def test_composition_scale_multiplies(self):
        """Scales multiply element-wise."""
        parent = GeneralPose3(scale=Vec3(2, 3, 4))
        child = GeneralPose3(scale=Vec3(5, 6, 7))

        result = parent * child

        assert_vec3_approx(result.scale, (10, 18, 28))

    def test_composition_non_uniform_scale(self):
        """Non-uniform scale affects position correctly."""
        parent = GeneralPose3(scale=Vec3(2, 1, 3))
        child = GeneralPose3(lin=Vec3(1, 1, 1))

        result = parent * child

        # Each axis scaled independently
        assert_vec3_approx(result.lin, (2, 1, 3))

    def test_composition_rotation_then_scale(self):
        """Parent rotation + scale affects child position."""
        # Parent: rotate 90 degrees around Z, then scale by 2
        parent = GeneralPose3.rotateZ(math.pi / 2)
        parent = parent.with_scale(Vec3(2, 2, 2))

        child = GeneralPose3(lin=Vec3(1, 0, 0))

        result = parent * child

        # Child [1,0,0] rotated 90 around Z -> [0,1,0], then scaled by 2 -> [0,2,0]
        assert_vec3_approx(result.lin, (0, 2, 0), eps=1e-5)

    def test_composition_translation_scale_child(self):
        """Parent translation + child with scale."""
        parent = GeneralPose3(lin=Vec3(10, 0, 0))
        child = GeneralPose3(lin=Vec3(1, 0, 0), scale=Vec3(3, 3, 3))

        result = parent * child

        # Parent translation + child position (no scale on parent)
        assert_vec3_approx(result.lin, (11, 0, 0))
        assert_vec3_approx(result.scale, (3, 3, 3))

    def test_composition_full_transform(self):
        """Full transform: translation + rotation + scale."""
        parent = GeneralPose3(
            lin=Vec3(10, 0, 0),
            ang=GeneralPose3.rotateZ(math.pi / 2).ang,
            scale=Vec3(2, 2, 2)
        )
        child = GeneralPose3(lin=Vec3(1, 0, 0))

        result = parent * child

        # Child [1,0,0] scaled by 2 -> [2,0,0], rotated 90 around Z -> [0,2,0],
        # then translated by [10,0,0] -> [10,2,0]
        assert_vec3_approx(result.lin, (10, 2, 0), eps=1e-5)

    def test_composition_chain_three_levels(self):
        """Chain of three transforms with scale."""
        level1 = GeneralPose3(scale=Vec3(2, 2, 2))
        level2 = GeneralPose3(lin=Vec3(1, 0, 0), scale=Vec3(3, 3, 3))
        level3 = GeneralPose3(lin=Vec3(1, 0, 0))

        result = level1 * level2 * level3

        # level3 [1,0,0] scaled by level2 scale [3,3,3] -> [3,0,0]
        # level2 position [1,0,0] + [3,0,0] = [4,0,0]
        # level2 result scaled by level1 scale [2,2,2] -> [8,0,0]
        # Final scale = [2,2,2] * [3,3,3] * [1,1,1] = [6,6,6]
        assert_vec3_approx(result.lin, (8, 0, 0))
        assert_vec3_approx(result.scale, (6, 6, 6))


class TestGeneralPose3Inverse:
    """Test inverse with scale."""

    def test_inverse_identity(self):
        gp = GeneralPose3.identity()
        inv = gp.inverse()
        assert_vec3_approx(inv.lin, (0, 0, 0))
        assert_vec3_approx(inv.scale, (1, 1, 1))

    def test_inverse_translation_only(self):
        gp = GeneralPose3(lin=Vec3(1, 2, 3))
        inv = gp.inverse()
        assert_vec3_approx(inv.lin, (-1, -2, -3))

    def test_inverse_scale_only(self):
        gp = GeneralPose3(scale=Vec3(2, 4, 8))
        inv = gp.inverse()
        assert_vec3_approx(inv.scale, (0.5, 0.25, 0.125))

    def test_inverse_roundtrip(self):
        """pose * inverse(pose) = identity (works for any scale)."""
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=Vec3(2, 3, 4)  # non-uniform scale OK for right multiplication
        )
        result = gp * gp.inverse()

        assert_vec3_approx(result.lin, (0, 0, 0), eps=1e-5)
        assert_vec3_approx(result.scale, (1, 1, 1), eps=1e-5)

    def test_inverse_roundtrip_reverse_uniform_scale(self):
        """inverse(pose) * pose = identity (uniform scale only).

        Note: Non-uniform scale with rotation doesn't form a closed group.
        TRS inverse is S^-1 R^-1 T^-1 which isn't representable as TRS
        when scale is non-uniform and rotation is present.
        """
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=Vec3(2, 2, 2)  # uniform scale
        )
        result = gp.inverse() * gp

        assert_vec3_approx(result.lin, (0, 0, 0), eps=1e-5)
        assert_vec3_approx(result.scale, (1, 1, 1), eps=1e-5)

    def test_inverse_roundtrip_reverse_no_rotation(self):
        """inverse(pose) * pose = identity (no rotation case).

        Works with non-uniform scale when there's no rotation.
        """
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            scale=Vec3(2, 3, 4)  # non-uniform, but no rotation
        )
        result = gp.inverse() * gp

        assert_vec3_approx(result.lin, (0, 0, 0), eps=1e-5)
        assert_vec3_approx(result.scale, (1, 1, 1), eps=1e-5)


class TestGeneralPose3TransformPoint:
    """Test point transformation with scale."""

    def test_transform_point_identity(self):
        gp = GeneralPose3.identity()
        point = Vec3(1, 2, 3)
        result = gp.transform_point(point)
        assert_vec3_approx(result, (1, 2, 3))

    def test_transform_point_scale_only(self):
        gp = GeneralPose3(scale=Vec3(2, 3, 4))
        point = Vec3(1, 1, 1)
        result = gp.transform_point(point)
        assert_vec3_approx(result, (2, 3, 4))

    def test_transform_point_translation_and_scale(self):
        gp = GeneralPose3(
            lin=Vec3(10, 20, 30),
            scale=Vec3(2, 2, 2)
        )
        point = Vec3(1, 1, 1)
        result = gp.transform_point(point)
        # scale first: [2,2,2], then translate: [12, 22, 32]
        assert_vec3_approx(result, (12, 22, 32))

    def test_inverse_transform_point_roundtrip(self):
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=Vec3(2, 3, 4)
        )
        point = Vec3(5, 6, 7)

        transformed = gp.transform_point(point)
        recovered = gp.inverse_transform_point(transformed)

        assert_vec3_approx(recovered, (5, 6, 7), eps=1e-5)


class TestGeneralPose3Matrix:
    """Test matrix conversion."""

    def test_as_matrix_identity(self):
        import numpy as np
        gp = GeneralPose3.identity()
        mat = gp.as_matrix()
        expected = np.eye(4)
        assert mat.shape == (4, 4)
        for i in range(4):
            for j in range(4):
                assert mat[i, j] == pytest.approx(expected[i, j])

    def test_as_matrix_scale(self):
        gp = GeneralPose3(scale=Vec3(2, 3, 4))
        mat = gp.as_matrix()

        # Scale should be in diagonal of rotation part
        assert mat[0, 0] == pytest.approx(2)
        assert mat[1, 1] == pytest.approx(3)
        assert mat[2, 2] == pytest.approx(4)

    def test_from_matrix_extracts_scale(self):
        import numpy as np
        # Create matrix with scale
        mat = np.array([
            [2, 0, 0, 1],
            [0, 3, 0, 2],
            [0, 0, 4, 3],
            [0, 0, 0, 1]
        ], dtype=float)

        gp = GeneralPose3.from_matrix(mat)

        assert_vec3_approx(gp.lin, (1, 2, 3))
        assert_vec3_approx(gp.scale, (2, 3, 4))

    def test_matrix_roundtrip(self):
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=Vec3(2, 3, 4)
        )
        mat = gp.as_matrix()
        gp2 = GeneralPose3.from_matrix(mat)

        assert_vec3_approx(gp2.lin, (gp.lin.x, gp.lin.y, gp.lin.z), eps=1e-5)
        assert_vec3_approx(gp2.scale, (gp.scale.x, gp.scale.y, gp.scale.z), eps=1e-5)


class TestGeneralPose3ToPose3:
    """Test conversion to Pose3."""

    def test_to_pose3_drops_scale(self):
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            ang=Quat(0, 0, 0, 1),
            scale=Vec3(2, 3, 4)
        )
        pose = gp.to_pose3()

        assert isinstance(pose, Pose3)
        assert_vec3_approx(pose.lin, (1, 2, 3))
        assert pose.ang.x == pytest.approx(0)
        assert pose.ang.y == pytest.approx(0)
        assert pose.ang.z == pytest.approx(0)
        assert pose.ang.w == pytest.approx(1)

    def test_pose3_to_general_pose3_roundtrip(self):
        pose = Pose3(
            lin=Vec3(1, 2, 3),
            ang=Pose3.rotateZ(0.5).ang
        )
        gp = pose.to_general_pose3(scale=Vec3(2, 2, 2))
        pose2 = gp.to_pose3()

        assert_vec3_approx(pose2.lin, (pose.lin.x, pose.lin.y, pose.lin.z))


class TestGeneralPose3Lerp:
    """Test interpolation with scale."""

    def test_lerp_position(self):
        gp1 = GeneralPose3(lin=Vec3(0, 0, 0))
        gp2 = GeneralPose3(lin=Vec3(10, 20, 30))

        result = GeneralPose3.lerp(gp1, gp2, 0.5)

        assert_vec3_approx(result.lin, (5, 10, 15))

    def test_lerp_scale(self):
        gp1 = GeneralPose3(scale=Vec3(1, 1, 1))
        gp2 = GeneralPose3(scale=Vec3(3, 5, 7))

        result = GeneralPose3.lerp(gp1, gp2, 0.5)

        assert_vec3_approx(result.scale, (2, 3, 4))

    def test_lerp_endpoints(self):
        gp1 = GeneralPose3(lin=Vec3(0, 0, 0), scale=Vec3(1, 1, 1))
        gp2 = GeneralPose3(lin=Vec3(10, 10, 10), scale=Vec3(2, 2, 2))

        result0 = GeneralPose3.lerp(gp1, gp2, 0.0)
        result1 = GeneralPose3.lerp(gp1, gp2, 1.0)

        assert_vec3_approx(result0.lin, (0, 0, 0))
        assert_vec3_approx(result0.scale, (1, 1, 1))
        assert_vec3_approx(result1.lin, (10, 10, 10))
        assert_vec3_approx(result1.scale, (2, 2, 2))
