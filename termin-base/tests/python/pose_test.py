import unittest
from termin.geombase import Pose3, Vec3, Quat, deg2rad
import numpy
import math


def assert_vec3_approx(actual, expected, places=6):
    """Helper to assert Vec3 is approximately equal to expected tuple or Vec3."""
    if isinstance(expected, Vec3):
        expected = (expected.x, expected.y, expected.z)
    assert abs(actual.x - expected[0]) < 10**(-places), f"x: {actual.x} != {expected[0]}"
    assert abs(actual.y - expected[1]) < 10**(-places), f"y: {actual.y} != {expected[1]}"
    assert abs(actual.z - expected[2]) < 10**(-places), f"z: {actual.z} != {expected[2]}"


def assert_quat_approx(actual, expected, places=6):
    """Helper to assert Quat is approximately equal to expected tuple or Quat."""
    if isinstance(expected, Quat):
        expected = (expected.x, expected.y, expected.z, expected.w)
    assert abs(actual.x - expected[0]) < 10**(-places), f"x: {actual.x} != {expected[0]}"
    assert abs(actual.y - expected[1]) < 10**(-places), f"y: {actual.y} != {expected[1]}"
    assert abs(actual.z - expected[2]) < 10**(-places), f"z: {actual.z} != {expected[2]}"
    assert abs(actual.w - expected[3]) < 10**(-places), f"w: {actual.w} != {expected[3]}"


class TestPose3(unittest.TestCase):
    def test_identity(self):
        pose = Pose3.identity()
        point = Vec3(1.0, 2.0, 3.0)
        transformed_point = pose.transform_point(point)
        assert_vec3_approx(transformed_point, point)

    def test_inverse(self):
        pose = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)),
            lin=Vec3(1.0, 2.0, 3.0)
        )
        inv_pose = pose.inverse()
        point = Vec3(4.0, 5.0, 6.0)
        transformed_point = pose.transform_point(point)
        recovered_point = inv_pose.transform_point(transformed_point)
        assert_vec3_approx(recovered_point, point)

    def test_inverse2(self):
        pose = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)),
            lin=Vec3(1.0, 2.0, 3.0)
        )
        inv_pose = pose.inverse()

        m = pose * inv_pose
        assert_vec3_approx(m.lin, (0, 0, 0))
        assert_quat_approx(m.ang, (0, 0, 0, 1))

        m = inv_pose*pose
        assert_vec3_approx(m.lin, (0, 0, 0))
        assert_quat_approx(m.ang, (0, 0, 0, 1))

    def test_inverse_3(self):
        pose = Pose3.translation(1, 0, 0) * Pose3.rotation(
            Vec3(1, 0, 0), deg2rad(10))
        inv_pose = pose.inverse()
        point = Vec3(4.0, 5.0, 6.0)
        transformed_point = pose.transform_point(point)
        recovered_point = inv_pose.transform_point(transformed_point)
        assert_vec3_approx(recovered_point, point)

    def test_rotation(self):
        angle = math.pi / 2  # 90 degrees
        pose = Pose3(
            ang=Quat(0.0, 0.0, math.sin(angle/2), math.cos(angle/2)),
            lin=Vec3(0.0, 0.0, 0.0)
        )
        point = Vec3(1.0, 0.0, 0.0)
        transformed_point = pose.transform_point(point)
        expected_point = Vec3(0.0, 1.0, 0.0)
        assert_vec3_approx(transformed_point, expected_point)

    def test_rotation_x(self):
        angle = math.pi / 2  # 90 degrees
        pose = Pose3(
            ang=Quat(math.sin(angle/2), 0.0, 0.0, math.cos(angle/2)),
            lin=Vec3(0.0, 0.0, 0.0)
        )
        point = Vec3(0.0, 0.0, 1.0)
        transformed_point = pose.transform_point(point)
        expected_point = Vec3(0.0, -1.0, 0.0)
        assert_vec3_approx(transformed_point, expected_point)

    def test_translation(self):
        pose = Pose3(
            ang=Quat(0.0, 0.0, 0.0, 1.0),
            lin=Vec3(1.0, 2.0, 3.0)
        )
        point = Vec3(4.0, 5.0, 6.0)
        transformed_point = pose.transform_point(point)
        expected_point = Vec3(5.0, 7.0, 9.0)
        assert_vec3_approx(transformed_point, expected_point)

    def test_composition(self):
        pose1 = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)),
            lin=Vec3(1.0, 0.0, 0.0)
        )
        pose2 = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)),
            lin=Vec3(0.0, 1.0, 0.0)
        )
        composed_pose = pose1 * pose2
        point = Vec3(1.0, 0.0, 0.0)
        transformed_point = composed_pose.transform_point(point)

        # Manually compute expected result
        intermediate_point = pose2.transform_point(point)
        expected_point = pose1.transform_point(intermediate_point)

        assert_vec3_approx(transformed_point, expected_point)

    def test_lerp(self):
        pose1 = Pose3(
            ang=Quat(0.0, 0.0, math.sin(0.0), math.cos(0.0)),
            lin=Vec3(0.0, 0.0, 0.0)
        )
        pose2 = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/2), math.cos(math.pi/2)),
            lin=Vec3(10.0, 0.0, 0.0)
        )
        t = 0.5
        lerped_pose = Pose3.lerp(pose1, pose2, t)

        point = Vec3(1.0, 0.0, 0.0)
        transformed_point = lerped_pose.transform_point(point)

        # Expected halfway rotation around Z and translation is (5, 0, 0)
        expected_rotation = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)),
            lin=Vec3(5.0, 0.0, 0.0)
        )
        expected_point = expected_rotation.transform_point(point)

        assert_vec3_approx(transformed_point, expected_point)

    def test_normalize(self):
        # Create a quaternion that's not normalized
        pose = Pose3(
            ang=Quat(1.0, 1.0, 1.0, 1.0),
            lin=Vec3(1.0, 2.0, 3.0)
        )
        pose = pose.normalized()
        # Check that quaternion is now unit length
        ang = pose.ang
        norm = math.sqrt(ang.x**2 + ang.y**2 + ang.z**2 + ang.w**2)
        self.assertAlmostEqual(norm, 1.0)

    def test_distance(self):
        pose1 = Pose3(
            ang=Quat(0.0, 0.0, 0.0, 1.0),
            lin=Vec3(1.0, 2.0, 3.0)
        )
        pose2 = Pose3(
            ang=Quat(0.0, 0.0, 0.0, 1.0),
            lin=Vec3(4.0, 6.0, 3.0)
        )
        distance = pose1.distance(pose2)
        expected_distance = math.sqrt((4-1)**2 + (6-2)**2 + (3-3)**2)
        self.assertAlmostEqual(distance, expected_distance)

    def test_axis_angle_conversion(self):
        # Create a rotation around Z axis by 90 degrees
        axis = Vec3(0.0, 0.0, 1.0)
        angle = math.pi / 2
        pose = Pose3.from_axis_angle(axis, angle)

        # Convert back to axis-angle
        result_axis, result_angle = pose.to_axis_angle()

        # Check the angle
        self.assertAlmostEqual(result_angle, angle)
        # Check the axis (should be normalized)
        assert_vec3_approx(result_axis, axis)

    def test_euler_conversion_xyz(self):
        # Create a pose from Euler angles
        roll = math.pi / 6   # 30 degrees
        pitch = math.pi / 4  # 45 degrees
        yaw = math.pi / 3    # 60 degrees

        pose = Pose3.from_euler(roll, pitch, yaw)

        # Convert back to Euler angles
        euler = pose.to_euler()
        result_roll, result_pitch, result_yaw = euler.x, euler.y, euler.z

        # Check that we get the same angles back
        self.assertAlmostEqual(result_roll, roll, places=6)
        self.assertAlmostEqual(result_pitch, pitch, places=6)
        self.assertAlmostEqual(result_yaw, yaw, places=6)

    def test_euler_consistency(self):
        # Test that rotation by Euler angles produces expected result
        pose = Pose3.from_euler(0, 0, math.pi / 2)  # 90 degrees around Z
        point = Vec3(1.0, 0.0, 0.0)
        transformed = pose.transform_point(point)
        expected = Vec3(0.0, 1.0, 0.0)
        assert_vec3_approx(transformed, expected)

    def test_looking_at(self):
        # Create a pose at origin looking towards (1, 0, 0)
        eye = Vec3(0.0, 0.0, 0.0)
        target = Vec3(1.0, 0.0, 0.0)
        up = Vec3(0.0, 0.0, 1.0)

        pose = Pose3.looking_at(eye, target, up)

        # Check that the pose is at the correct position
        assert_vec3_approx(pose.lin, eye)

        # The Z axis (local up, index 2 in rotation matrix) should align with world up
        rot_mat = pose.rotation_matrix()
        local_up = numpy.array([rot_mat[0, 2], rot_mat[1, 2], rot_mat[2, 2]])  # Column 2 is the up direction
        numpy.testing.assert_array_almost_equal(
            local_up,
            numpy.array([up.x, up.y, up.z]),
            decimal=5
        )

    def test_properties_xyz(self):
        pose = Pose3(
            ang=Quat(0.0, 0.0, 0.0, 1.0),
            lin=Vec3(1.0, 2.0, 3.0)
        )

        # Test getters
        self.assertAlmostEqual(pose.x, 1.0)
        self.assertAlmostEqual(pose.y, 2.0)
        self.assertAlmostEqual(pose.z, 3.0)

        # Test setters
        pose.x = 4.0
        pose.y = 5.0
        pose.z = 6.0

        assert_vec3_approx(pose.lin, (4.0, 5.0, 6.0))

    def test_as_matrix34(self):
        pose = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)),
            lin=Vec3(1.0, 2.0, 3.0)
        )
        mat34 = pose.as_matrix34()

        # Check shape
        self.assertEqual(mat34.shape, (3, 4))

        # Check that rotation part matches 3x3 rotation matrix
        rot_mat = pose.rotation_matrix()
        numpy.testing.assert_array_almost_equal(mat34[:, :3], rot_mat)

        # Check that translation part is correct
        numpy.testing.assert_array_almost_equal(mat34[:, 3], [pose.lin.x, pose.lin.y, pose.lin.z])

    def test_transform_vector(self):
        # Test that transform_vector ignores translation
        pose = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/2), math.cos(math.pi/2)),
            lin=Vec3(10.0, 20.0, 30.0)
        )
        vector = Vec3(1.0, 0.0, 0.0)
        transformed = pose.transform_vector(vector)
        assert_vec3_approx(transformed, (-1.0, 0.0, 0.0))

    def test_inverse_transform_vector(self):
        pose = Pose3(
            ang=Quat(0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)),
            lin=Vec3(1.0, 2.0, 3.0)
        )
        vector = Vec3(1.0, 0.0, 0.0)

        # Transform and inverse transform should give back original
        transformed = pose.transform_vector(vector)
        recovered = pose.inverse_transform_vector(transformed)
        assert_vec3_approx(recovered, vector)

    def test_compose_method(self):
        # Test that compose() method works same as * operator
        pose1 = Pose3.rotateZ(math.pi / 4) * Pose3.translation(1.0, 0.0, 0.0)
        pose2 = Pose3.rotateX(math.pi / 6)

        result1 = pose1 * pose2
        result2 = pose1.compose(pose2)

        assert_quat_approx(result1.ang, result2.ang)
        assert_vec3_approx(result1.lin, result2.lin)

    def test_rotation_matrices(self):
        # Test rotateX, rotateY, rotateZ produce correct rotations

        # 90 degree rotation around X
        pose_x = Pose3.rotateX(math.pi / 2)
        point = Vec3(0.0, 1.0, 0.0)
        transformed = pose_x.transform_point(point)
        expected = Vec3(0.0, 0.0, 1.0)
        assert_vec3_approx(transformed, expected)

        # 90 degree rotation around Y
        pose_y = Pose3.rotateY(math.pi / 2)
        point = Vec3(0.0, 0.0, 1.0)
        transformed = pose_y.transform_point(point)
        expected = Vec3(1.0, 0.0, 0.0)
        assert_vec3_approx(transformed, expected)

        # 90 degree rotation around Z
        pose_z = Pose3.rotateZ(math.pi / 2)
        point = Vec3(1.0, 0.0, 0.0)
        transformed = pose_z.transform_point(point)
        expected = Vec3(0.0, 1.0, 0.0)
        assert_vec3_approx(transformed, expected)

    def test_static_move_methods(self):
        # Test moveX, moveY, moveZ, right, forward, up
        # Test moveX and right (should be same)
        pose = Pose3.moveX(5.0)
        self.assertAlmostEqual(pose.x, 5.0)
        pose = Pose3.right(5.0)
        self.assertAlmostEqual(pose.x, 5.0)

        # Test moveY and forward (should be same)
        pose = Pose3.moveY(3.0)
        self.assertAlmostEqual(pose.y, 3.0)
        pose = Pose3.forward(3.0)
        self.assertAlmostEqual(pose.y, 3.0)

        # Test moveZ and up (should be same)
        pose = Pose3.moveZ(7.0)
        self.assertAlmostEqual(pose.z, 7.0)
        pose = Pose3.up(7.0)
        self.assertAlmostEqual(pose.z, 7.0)

    def test_complex_composition(self):
        # Test a complex sequence of transformations
        pose = (Pose3.translation(1.0, 0.0, 0.0) *
                Pose3.rotateZ(math.pi / 2) *
                Pose3.translation(2.0, 0.0, 0.0))

        point = Vec3(0.0, 0.0, 0.0)
        result = pose.transform_point(point)

        # Manually compute expected result
        # Start at origin
        # Translate by (2, 0, 0) -> (2, 0, 0)
        # Rotate 90 degrees around Z -> (0, 2, 0)
        # Translate by (1, 0, 0) -> (1, 2, 0)
        expected = Vec3(1.0, 2.0, 0.0)
        assert_vec3_approx(result, expected)
