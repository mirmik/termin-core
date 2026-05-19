"""TransformAABB - AABB associated with a Transform."""

import numpy
from weakref import WeakKeyDictionary
from ._geom_native import AABB


class TransformAABB:
    """AABB associated with a Transform."""
    transform_to_taabb_map = WeakKeyDictionary()

    __slots__ = ('_transform', '_my_aabb', '_my_world_aabb', '_compiled_aabb',
                 '_last_inspected_version', '_last_tree_inspected_version')

    def __init__(self, transform: 'Transform', aabb: AABB):
        self._transform = transform
        self._my_aabb = aabb
        self._my_world_aabb = None
        self._compiled_aabb = None
        self._last_inspected_version = -1
        self._last_tree_inspected_version = -1
        TransformAABB.transform_to_taabb_map[transform] = self

    def compile_tree_aabb(self) -> AABB:
        if self._last_tree_inspected_version == self._transform._version_for_walking_to_distal:
            return self._compiled_aabb
        result = self.get_world_aabb()
        for child in self._transform.children:
            child_taabb = TransformAABB.transform_to_taabb_map.get(child)
            if child_taabb:
                child_aabb = child_taabb.compile_tree_aabb()
                result = result.merge(child_aabb)
        self._compiled_aabb = result
        self._last_tree_inspected_version = self._transform._version_for_walking_to_distal
        return self._compiled_aabb

    def get_world_aabb(self) -> AABB:
        """Get the AABB widened by the rotation of the transform."""
        if self._last_inspected_version == self._transform._version_only_my:
            return self._my_world_aabb
        matrix = self._transform.global_pose().as_matrix()[:3, :]  # 3x4 from 4x4
        corners = self._my_aabb.get_corners_homogeneous()
        transformed_corners = numpy.dot(matrix, corners.T).T
        new_aabb = AABB.from_points(transformed_corners)
        self._my_world_aabb = new_aabb
        return new_aabb
