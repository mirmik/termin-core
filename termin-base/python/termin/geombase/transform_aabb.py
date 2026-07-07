"""TransformAABB - AABB associated with a Transform."""
from weakref import WeakKeyDictionary
from ._geom_native import AABB


class TransformAABB:
    """AABB associated with a Transform."""
    transform_to_taabb_map = WeakKeyDictionary()

    __slots__ = ('_transform', '_my_aabb', '_my_world_aabb', '_compiled_aabb',
                 '_last_inspected_version', '_last_tree_inspected_version')

    def __init__(self, transform, aabb: AABB):
        self._transform = transform
        self._my_aabb = aabb
        self._my_world_aabb = None
        self._compiled_aabb = None
        self._last_inspected_version = -1
        self._last_tree_inspected_version = -1
        TransformAABB.transform_to_taabb_map[transform] = self

    def compile_tree_aabb(self) -> AABB:
        inspected_version = (
            self._transform._version_for_walking_to_distal,
            self._transform._version_for_walking_to_proximal,
        )
        if self._last_tree_inspected_version == inspected_version:
            return self._compiled_aabb
        result = self.get_world_aabb()
        for child in self._transform.children:
            child_taabb = TransformAABB.transform_to_taabb_map.get(child)
            if child_taabb:
                child_aabb = child_taabb.compile_tree_aabb()
                result = result.merge(child_aabb)
        self._compiled_aabb = result
        self._last_tree_inspected_version = inspected_version
        return self._compiled_aabb

    def get_world_aabb(self) -> AABB:
        """Get the AABB widened by the rotation of the transform."""
        inspected_version = self._transform._version_for_walking_to_proximal
        if self._last_inspected_version == inspected_version:
            return self._my_world_aabb
        new_aabb = self._my_aabb.transformed_by(self._transform.global_pose())
        self._my_world_aabb = new_aabb
        self._last_inspected_version = inspected_version
        return new_aabb
