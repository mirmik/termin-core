import math
import numpy


class Pose2:
    """A 2D Pose represented by rotation angle and translation vector."""

    __slots__ = ('ang', 'lin', '_rot_matrix', '_mat')

    def __init__(self, ang: float = 0.0, lin: numpy.ndarray = numpy.array([0.0, 0.0])):
        """
        Args:
            ang: Rotation angle in radians
            lin: Translation vector [x, y]
        """
        self.ang = ang
        self.lin = numpy.asarray(lin)
        if self.lin.shape != (2,):
            raise ValueError("lin must be a 2D vector")
        self._rot_matrix = None  # Lazy computation
        self._mat = None  # Lazy computation

    def copy(self) -> 'Pose2':
        """Create a copy of the Pose2."""
        return Pose2(ang=self.ang, lin=self.lin.copy())

    @staticmethod
    def identity():
        """Create an identity pose (no rotation, no translation)."""
        return Pose2(ang=0.0, lin=numpy.array([0.0, 0.0]))

    def rotation_matrix(self):
        """Get the 2x2 rotation matrix corresponding to the pose's orientation."""
        if self._rot_matrix is None:
            c = math.cos(self.ang)
            s = math.sin(self.ang)
            self._rot_matrix = numpy.array([
                [c, -s],
                [s,  c]
            ])
        return self._rot_matrix

    def as_matrix(self):
        """Get the 3x3 transformation matrix corresponding to the pose."""
        if self._mat is None:
            R = self.rotation_matrix()
            t = self.lin
            self._mat = numpy.eye(3)
            self._mat[:2, :2] = R
            self._mat[:2, 2] = t
        return self._mat

    def inverse(self):
        """Compute the inverse of the pose."""
        inv_ang = -self.ang
        c = math.cos(inv_ang)
        s = math.sin(inv_ang)
        # Rotate translation by inverse rotation
        inv_lin = numpy.array([
            c * (-self.lin[0]) - s * (-self.lin[1]),
            s * (-self.lin[0]) + c * (-self.lin[1])
        ])
        return Pose2(inv_ang, inv_lin)

    def __repr__(self):
        return f"Pose2(ang={self.ang}, lin={self.lin})"

    def transform_point(self, point: numpy.ndarray) -> numpy.ndarray:
        """Transform a 2D point using the pose."""
        point = numpy.asarray(point)
        if point.shape != (2,):
            raise ValueError("point must be a 2D vector")
        R = self.rotation_matrix()
        return R @ point + self.lin

    def transform_vector(self, vector: numpy.ndarray) -> numpy.ndarray:
        """Transform a 2D vector using the pose (ignoring translation)."""
        vector = numpy.asarray(vector)
        if vector.shape != (2,):
            raise ValueError("vector must be a 2D vector")
        R = self.rotation_matrix()
        return R @ vector

    def rotate_vector(self, vector: numpy.ndarray) -> numpy.ndarray:
        """Rotate a 2D vector using the pose's rotation."""
        vector = numpy.asarray(vector)
        if vector.shape != (2,):
            raise ValueError("vector must be a 2D vector")
        R = self.rotation_matrix()
        return R @ vector

    def inverse_transform_point(self, point: numpy.ndarray) -> numpy.ndarray:
        """Transform a 2D point using the inverse of the pose."""
        point = numpy.asarray(point)
        point = point.reshape(2)
        R = self.rotation_matrix()
        return R.T @ (point - self.lin)

    def inverse_rotate_vector(self, vector: numpy.ndarray) -> numpy.ndarray:
        """Rotate a 2D vector using the inverse of the pose's rotation."""
        vector = numpy.asarray(vector)
        if vector.shape != (2,):
            raise ValueError("vector must be a 2D vector")
        R = self.rotation_matrix()
        return R.T @ vector

    def inverse_transform_vector(self, vector: numpy.ndarray) -> numpy.ndarray:
        """Transform a 2D vector using the inverse of the pose (ignoring translation)."""
        vector = numpy.asarray(vector)
        if vector.shape != (2,):
            raise ValueError("vector must be a 2D vector")
        R = self.rotation_matrix()
        return R.T @ vector

    def __mul__(self, other):
        """Compose this pose with another pose."""
        if not isinstance(other, Pose2):
            raise TypeError("Can only multiply Pose2 with Pose2")
        # Compose rotations: angles add
        new_ang = self.ang + other.ang
        # Compose translations: rotate other's translation and add to self's
        R = self.rotation_matrix()
        new_lin = self.lin + R @ other.lin
        return Pose2(ang=new_ang, lin=new_lin)

    def __matmul__(self, other):
        """Compose this pose with another pose using @ operator."""
        return self * other

    def compose(self, other: 'Pose2') -> 'Pose2':
        """Compose this pose with another pose."""
        return self * other

    @staticmethod
    def rotation(angle: float):
        """Create a rotation pose by a given angle."""
        return Pose2(ang=angle, lin=numpy.array([0.0, 0.0]))

    @staticmethod
    def translation(x: float, y: float):
        """Create a translation pose."""
        return Pose2(ang=0.0, lin=numpy.array([x, y]))

    @staticmethod
    def move(dx: float, dy: float):
        """Move the pose by given deltas in local coordinates."""
        return Pose2.translation(dx, dy)

    @staticmethod
    def moveX(distance: float):
        """Move along X axis."""
        return Pose2.move(distance, 0.0)

    @staticmethod
    def moveY(distance: float):
        """Move along Y axis."""
        return Pose2.move(0.0, distance)

    @staticmethod
    def right(distance: float):
        """Move right (along X axis)."""
        return Pose2.move(distance, 0.0)

    @staticmethod
    def forward(distance: float):
        """Move forward (along Y axis)."""
        return Pose2.move(0.0, distance)

    @staticmethod
    def lerp(pose1: 'Pose2', pose2: 'Pose2', t: float) -> 'Pose2':
        """Linearly interpolate between two poses."""
        lerped_ang = (1 - t) * pose1.ang + t * pose2.ang
        lerped_lin = (1 - t) * pose1.lin + t * pose2.lin
        return Pose2(ang=lerped_ang, lin=lerped_lin)

    def normalize_angle(self):
        """Normalize the angle to [-π, π]."""
        self.ang = math.atan2(math.sin(self.ang), math.cos(self.ang))
        self._rot_matrix = None
        self._mat = None

    @property
    def x(self):
        """Get X coordinate of translation."""
        return self.lin[0]

    @property
    def y(self):
        """Get Y coordinate of translation."""
        return self.lin[1]

    @x.setter
    def x(self, value: float):
        """Set X coordinate of translation."""
        self.lin[0] = value
        self._mat = None

    @y.setter
    def y(self, value: float):
        """Set Y coordinate of translation."""
        self.lin[1] = value
        self._mat = None
