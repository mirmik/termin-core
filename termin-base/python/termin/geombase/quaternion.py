"""Quaternion helpers kept as thin adapters around native Quat."""

from __future__ import annotations

import math

from ._geom_native import Quat, Vec3, slerp


def _quat(value) -> Quat:
    if isinstance(value, Quat):
        return value
    return Quat(value[0], value[1], value[2], value[3])


def _vec3(value) -> Vec3:
    if isinstance(value, Vec3):
        return value
    return Vec3(value[0], value[1], value[2])


def qmul(q1, q2) -> Quat:
    """Multiply two quaternions."""
    return _quat(q1) * _quat(q2)


def qmul_vector(q, v) -> Quat:
    """Multiply quaternion q by a pure-vector quaternion [v.x, v.y, v.z, 0]."""
    vec = _vec3(v)
    return _quat(q) * Quat(vec.x, vec.y, vec.z, 0.0)


def qrot(q, v) -> Vec3:
    """Rotate vector v by quaternion q."""
    return _quat(q).rotate(_vec3(v))


def qslerp(q1, q2, t: float) -> Quat:
    """Spherical linear interpolation between two quaternions."""
    return slerp(_quat(q1), _quat(q2), t)


def deg2rad(deg):
    return deg / 180.0 * math.pi


def qinv(q) -> Quat:
    """Compute the inverse of a quaternion."""
    return _quat(q).inverse()


__all__ = ["deg2rad", "qinv", "qmul", "qmul_vector", "qrot", "qslerp"]
