import numpy
from termin.geombase._geom_native import Screw3 as _NativeScrew3, Vec3
from termin.geombase.pose2 import Pose2

Screw3 = _NativeScrew3

__all__ = ["Screw", "Screw2", "Screw3"]

def _to_numpy(v):
    """Convert Vec3 or array-like to numpy array."""
    if isinstance(v, numpy.ndarray):
        return v
    if isinstance(v, Vec3):
        return numpy.array([v.x, v.y, v.z], dtype=numpy.float64)
    return numpy.asarray(v, dtype=numpy.float64)

def cross2d(scalar, vec):
    """2D cross product: scalar × vector = [vy, -vx] * scalar"""
    return scalar * numpy.array([vec[1], -vec[0]])

def cross2d_scalar(vec1, vec2):
    """2D cross product returning scalar: vec1 × vec2 = v1x*v2y - v1y*v2x"""
    return vec1[0]*vec2[1] - vec1[1]*vec2[0]

def cross2d_xz(vec, scalar):
    """2D cross product for twist transformation: vector × scalar = [-sy, sx]"""
    return numpy.array([-scalar * vec[1], scalar * vec[0]])

class Screw:
    """A class representing a pair of vector and bivector"""

    __slots__ = ('ang', 'lin')

    def __init__(self, ang, lin):
        # Convert to numpy if needed
        self.ang = _to_numpy(ang)  # Bivector part
        self.lin = _to_numpy(lin)  # Vector part

    def __repr__(self):
        return f"Screw(ang={self.ang}, lin={self.lin})"

class Screw2(Screw):
    """A 2D Screw specialized for planar motions."""

    __slots__ = ()

    def __init__(self, ang: numpy.ndarray, lin: numpy.ndarray):

        if not isinstance(ang, numpy.ndarray):
            ang = numpy.array(ang)
        ang = ang.reshape(1)
        lin = lin.reshape(2)

        super().__init__(ang=ang, lin=lin)

    def copy(self) -> "Screw2":
        """Create a copy of the Screw2."""
        return Screw2(ang=self.ang.copy(), lin=self.lin.copy())

    def moment(self) -> float:
        """Return the moment (bivector part) of the screw."""
        return self.ang.item() if self.ang.shape == () or self.ang.shape == (1,) else self.ang[0]

    def vector(self) -> numpy.ndarray:
        """Return the vector part of the screw."""
        return self.lin

    def kinematic_carry(self, arm: numpy.ndarray) -> "Screw2":
        """Twist transform. Carry the screw by arm. For pair of angular and linear speeds."""
        return Screw2(
            lin=self.lin + cross2d(self.moment(), arm),
            ang=self.ang)

    def force_carry(self, arm: numpy.ndarray) -> "Screw2":
        """Wrench transform. Carry the screw by arm. For pair of torques and forces."""
        return Screw2(
            ang=self.ang - numpy.array([cross2d_scalar(arm, self.lin)]),
            lin=self.lin)

    def twist_carry(self, arm: numpy.ndarray) -> "Screw2":
        """Alias for kinematic_carry."""
        return self.kinematic_carry(arm)

    def wrench_carry(self, arm: numpy.ndarray) -> "Screw2":
        """Alias for force_carry."""
        return self.force_carry(arm)

    def transform_by(self, trans):
        return Screw2(ang=self.ang, lin=trans.transform_vector(self.lin))

    def rotated_by(self, trans):
        return Screw2(ang=self.ang, lin=trans.rotate_vector(self.lin))

    def inverse_transform_by(self, trans):
        return Screw2(ang=self.ang, lin=trans.inverse_transform_vector(self.lin))

    def transform_as_twist_by(self, trans):
        rlin = trans.transform_vector(self.lin)
        return Screw2(
            lin=rlin + cross2d_xz(trans.lin, self.moment()),
            ang=self.ang,
        )

    def inverse_transform_as_twist_by(self, trans):
        return Screw2(
            ang=self.ang,
            lin=trans.inverse_transform_vector(self.lin - cross2d_xz(trans.lin, self.moment()))
        )

    def transform_as_wrench_by(self, trans):
        """Transform wrench (moment + force) under SE(2) transform."""
        return Screw2(
            ang=self.ang + numpy.array([cross2d_scalar(trans.lin, self.lin)]),
            lin=trans.transform_vector(self.lin)
        )

    def inverse_transform_as_wrench_by(self, trans):
        """Inverse transform of a wrench under SE(2) transform."""
        return Screw2(
            ang=self.ang - numpy.array([cross2d_scalar(trans.lin, self.lin)]),
            lin=trans.inverse_transform_vector(self.lin)
        )

    def __mul__(self, oth):
        return Screw2(self.ang * oth, self.lin * oth)

    def __add__(self, oth):
        return Screw2(self.ang + oth.ang, self.lin + oth.lin)

    def __sub__(self, oth):
        return Screw2(self.ang - oth.ang, self.lin - oth.lin)

    def to_vector_vw_order(self) -> numpy.ndarray:
        """Return the screw as a 3x1 array in [vx, vy, w] order."""
        return numpy.array([self.lin[0], self.lin[1], self.moment()], float)

    def to_vector_wv_order(self) -> numpy.ndarray:
        """Return the screw as a 3x1 array in [w, vx, vy] order."""
        return numpy.array([self.moment(), self.lin[0], self.lin[1]], float)

    def from_vector_vw_order(vec: numpy.ndarray) -> "Screw2":
        """Create a Screw2 from a 3x1 array in [vx, vy, w] order."""
        if vec.shape != (3,):
            raise Exception("Input vector must be of shape (3,)")

        return Screw2(
            ang=numpy.array([vec[2]]),
            lin=numpy.array([vec[0], vec[1]])
        )

    def from_vector_wv_order(vec: numpy.ndarray) -> "Screw2":
        """Create a Screw2 from a 3x1 array in [w, vx, vy] order."""
        if vec.shape != (3,):
            raise Exception("Input vector must be of shape (3,)")

        return Screw2(
            ang=numpy.array([vec[0]]),
            lin=numpy.array([vec[1], vec[2]])
        )

    def to_pose(self):
        """Convert the screw to a Pose2 representation (for small motions)."""
        return Pose2(
            ang=self.moment(),
            lin=self.lin
        )
