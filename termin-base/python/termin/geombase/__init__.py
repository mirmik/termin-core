"""
Базовые геометрические классы (Geometric Base).

Содержит фундаментальные классы для представления геометрии:
- Pose2 - позы (положение + ориентация) в 2D пространстве
- Pose3 - позы (положение + ориентация) в 3D пространстве
- GeneralPose3 - позы с масштабированием
- Screw, Screw2, Screw3 - винтовые преобразования

Использует скомпилированный C++ модуль для Pose3, GeneralPose3 и связанных типов.
"""

# Import C++ native implementations
from ._geom_native import (
    Vec3,
    Vec4,
    Quat,
    Mat44,
    Mat44f,
    Pose3,
    GeneralPose3,
    Screw3,
    AABB,
    OrbitCamera,
)

from .pose2 import Pose2
from .quaternion import deg2rad, qinv, qmul, qmul_vector, qrot, qslerp
from .screw import Screw, Screw2
from .transform_aabb import TransformAABB

__all__ = [
    'Vec3',
    'Vec4',
    'Quat',
    'Mat44',
    'Mat44f',
    'Pose2',
    'Pose3',
    'GeneralPose3',
    'Screw',
    'Screw2',
    'Screw3',
    'AABB',
    'OrbitCamera',
    'TransformAABB',
    'deg2rad',
    'qinv',
    'qmul',
    'qmul_vector',
    'qrot',
    'qslerp',
]
