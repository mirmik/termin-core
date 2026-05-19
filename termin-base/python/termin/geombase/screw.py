import numpy
import math
from termin.geombase._geom_native import Pose3, Vec3

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

    def kinematic_carry(self, arm: "Vector2") -> "Screw2":
        """Twist transform. Carry the screw by arm. For pair of angular and linear speeds."""
        return Screw2(
            lin=self.lin + cross2d(self.moment(), arm),
            ang=self.ang)

    def force_carry(self, arm: "Vector2") -> "Screw2":
        """Wrench transform. Carry the screw by arm. For pair of torques and forces."""
        return Screw2(
            ang=self.ang - numpy.array([cross2d_scalar(arm, self.lin)]),
            lin=self.lin)

    def twist_carry(self, arm: "Vector2") -> "Screw2":
        """Alias for kinematic_carry."""
        return self.kinematic_carry(arm)

    def wrench_carry(self, arm: "Vector2") -> "Screw2":
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

class Screw3(Screw):
    """A 3D Screw specialized for spatial motions."""

    __slots__ = ()

    def __init__(self, ang: numpy.ndarray = numpy.array([0,0,0]), lin: numpy.ndarray = numpy.array([0,0,0])):
        super().__init__(ang=ang, lin=lin)

    @staticmethod
    def zero() -> "Screw3":
        """Create a zero screw."""
        return Screw3(ang=numpy.zeros(3, dtype=numpy.float64), lin=numpy.zeros(3, dtype=numpy.float64))

    def copy(self) -> "Screw3":
        """Create a copy of the Screw3."""
        return Screw3(ang=self.ang.copy(), lin=self.lin.copy())

    def moment(self) -> numpy.ndarray:
        """Return the moment (bivector part) of the screw."""
        return self.ang

    def vector(self) -> numpy.ndarray:
        """Return the vector part of the screw."""
        return self.lin

    def kinematic_carry(self, arm: "Vector3") -> "Screw3":
        """Twist transform. Carry the screw by arm. For pair of angular and linear speeds."""
        return Screw3(
            lin=self.lin + numpy.cross(self.ang, arm),
            ang=self.ang)

    def force_carry(self, arm: "Vector3") -> "Screw3":
        """Wrench transform. Carry the screw by arm. For pair of torques and forces."""
        return Screw3(
            ang=self.ang - numpy.cross(arm, self.lin),
            lin=self.lin)

    def twist_carry(self, arm: "Vector3") -> "Screw3":
        """Alias for kinematic_carry."""
        return self.kinematic_carry(arm)

    def wrench_carry(self, arm: "Vector3") -> "Screw3":
        """Alias for force_carry."""
        return self.force_carry(arm)

    def transform_by(self, trans):
        return Screw3(
            ang=_to_numpy(trans.transform_vector(self.ang)),
            lin=_to_numpy(trans.transform_vector(self.lin))
        )

    def rotate_by(self, rot):
        return Screw3(
            ang=_to_numpy(rot.transform_vector(self.ang)),
            lin=_to_numpy(rot.transform_vector(self.lin))
        )

    def inverse_rotate_by(self, rot):
        return Screw3(
            ang=_to_numpy(rot.inverse_transform_vector(self.ang)),
            lin=_to_numpy(rot.inverse_transform_vector(self.lin))
        )

    def inverse_transform_by(self, trans):
        return Screw3(
            ang=_to_numpy(trans.inverse_transform_vector(self.ang)),
            lin=_to_numpy(trans.inverse_transform_vector(self.lin))
        )

    def transform_as_twist_by(self, trans):
        rang = _to_numpy(trans.transform_vector(self.ang))
        trans_lin = _to_numpy(trans.lin) if isinstance(trans.lin, Vec3) else trans.lin
        return Screw3(
            ang = rang,
            lin = _to_numpy(trans.transform_vector(self.lin)) + numpy.cross(trans_lin, rang)
        )

    def inverse_transform_as_twist_by(self, trans):
        trans_lin = _to_numpy(trans.lin) if isinstance(trans.lin, Vec3) else trans.lin
        return Screw3(
            ang = _to_numpy(trans.inverse_transform_vector(self.ang)),
            lin = _to_numpy(trans.inverse_transform_vector(self.lin - numpy.cross(trans_lin, self.ang)))
        )

    def transform_as_wrench_by(self, trans):
        """Transform wrench (moment + force) under SE(3) transform."""
        p = _to_numpy(trans.lin) if isinstance(trans.lin, Vec3) else trans.lin
        return Screw3(
            ang = _to_numpy(trans.transform_vector(self.ang + numpy.cross(p, self.lin))),
            lin = _to_numpy(trans.transform_vector(self.lin))
        )

    def inverse_transform_as_wrench_by(self, trans):
        """Inverse transform of a wrench under SE(3) transform."""
        p = _to_numpy(trans.lin) if isinstance(trans.lin, Vec3) else trans.lin
        return Screw3(
            ang = _to_numpy(trans.inverse_transform_vector(self.ang - numpy.cross(p, self.lin))),
            lin = _to_numpy(trans.inverse_transform_vector(self.lin))
        )

    def as_pose3(self):
        """Convert the screw to a Pose3 representation (for small motions)."""
        rotangle = numpy.linalg.norm(self.ang)
        if rotangle < 1e-8:
            # Pure translation
            return Pose3(
                ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
                lin=self.lin
            )
        axis = self.ang / rotangle
        half_angle = rotangle / 2.0
        q = numpy.array([
            axis[0] * math.sin(half_angle),
            axis[1] * math.sin(half_angle),
            axis[2] * math.sin(half_angle),
            math.cos(half_angle)
        ])
        return Pose3(
            ang=q,
            lin=self.lin
        )

    def __mul__(self, oth):
        return Screw3(self.ang * oth, self.lin * oth)

    def __rmul__(self, oth):
        return Screw3(self.ang * oth, self.lin * oth)

    def __add__(self, oth):
        return Screw3(self.ang + oth.ang, self.lin + oth.lin)

    def __sub__(self, oth):
        return Screw3(self.ang - oth.ang, self.lin - oth.lin)

    def __neg__(self):
        return Screw3(-self.ang, -self.lin)

    def dot(self, oth: "Screw3") -> float:
        """Dot product of two screws (for power computation: wrench · twist)."""
        return numpy.dot(self.ang, oth.ang) + numpy.dot(self.lin, oth.lin)

    def cross_motion(self, oth: "Screw3") -> "Screw3":
        """
        Spatial cross product for motion vectors (twist × twist).
        [ω₁ × ω₂, ω₁ × v₂ + v₁ × ω₂]
        """
        return Screw3(
            ang=numpy.cross(self.ang, oth.ang),
            lin=numpy.cross(self.ang, oth.lin) + numpy.cross(self.lin, oth.ang)
        )

    def cross_force(self, oth: "Screw3") -> "Screw3":
        """
        Spatial cross product for force vectors (twist ×* wrench).
        [ω × τ + v × f, ω × f]
        """
        return Screw3(
            ang=numpy.cross(self.ang, oth.ang) + numpy.cross(self.lin, oth.lin),
            lin=numpy.cross(self.ang, oth.lin)
        )

    def to_vw_array(self) -> numpy.ndarray:
        """Return the screw as a 6x1 array in [vx, vy, vz, wx, wy, wz] order."""
        return numpy.hstack([self.lin, self.ang])

    def to_wv_array(self) -> numpy.ndarray:
        """Return the screw as a 6x1 array in [wx, wy, wz, vx, vy, vz] order."""
        return numpy.hstack([self.ang, self.lin])

    def from_vw_array(vec: numpy.ndarray) -> "Screw3":
        """Create a Screw3 from a 6x1 array in [vx, vy, vz, wx, wy, wz] order."""
        if vec.shape != (6,):
            raise Exception("Input vector must be of shape (6,)")

        return Screw3(
            ang=vec[3:6],
            lin=vec[0:3]
        )
    def from_wv_array(vec: numpy.ndarray) -> "Screw3":
        """Create a Screw3 from a 6x1 array in [wx, wy, wz, vx, vy, vz] order."""
        if vec.shape != (6,):
            raise Exception("Input vector must be of shape (6,)")

        return Screw3(
            ang=vec[0:3],
            lin=vec[3:6]
        )

    def to_pose(self):
        """Convert the screw to a Pose3 representation (for small motions)."""
        lin = self.lin

        #exponential map for rotation
        theta = numpy.linalg.norm(self.ang)
        if theta < 1e-8:
            # Pure translation
            return Pose3(
                ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
                lin=lin
            )
        axis = self.ang / theta
        half_angle = theta / 2.0
        q = numpy.array([
            axis[0] * math.sin(half_angle),
            axis[1] * math.sin(half_angle),
            axis[2] * math.sin(half_angle),
            math.cos(half_angle)
        ])
        return Pose3(
            ang=q,
            lin=lin
        )

    def from_vector_vw_order(vec: numpy.ndarray) -> "Screw3":
        """Create a Screw3 from a 6x1 array in [vx, vy, vz, wx, wy, wz] order."""
        if vec.shape != (6,):
            raise Exception("Input vector must be of shape (6,)")

        return Screw3(
            ang=vec[3:6],
            lin=vec[0:3]
        )

    def from_vector_wv_order(vec: numpy.ndarray) -> "Screw3":
        """Create a Screw3 from a 6x1 array in [wx, wy, wz, vx, vy, vz] order."""
        if vec.shape != (6,):
            raise Exception("Input vector must be of shape (6,)")

        return Screw3(
            ang=vec[0:3],
            lin=vec[3:6]
        )

    def to_vector_vw_order(self) -> numpy.ndarray:
        """Return the screw as a 6x1 array in [vx, vy, vz, wx, wy, wz] order."""
        return numpy.array([self.lin[0], self.lin[1], self.lin[2],
                            self.ang[0], self.ang[1], self.ang[2]], float)

    def to_vector_wv_order(self) -> numpy.ndarray:
        """Return the screw as a 6x1 array in [wx, wy, wz, vx, vy, vz] order."""
        return numpy.array([self.ang[0], self.ang[1], self.ang[2],
                            self.lin[0], self.lin[1], self.lin[2]], float)