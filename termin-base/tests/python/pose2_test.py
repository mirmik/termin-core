import unittest
import numpy as np
import math
from termin.geombase import Pose2


class TestPose2(unittest.TestCase):
    """Тесты для класса Pose2"""

    def test_identity(self):
        """Тест создания единичной позы"""
        pose = Pose2.identity()
        self.assertEqual(pose.ang, 0.0)
        np.testing.assert_array_equal(list(pose.lin), np.array([0.0, 0.0]))

    def test_rotation_matrix(self):
        """Тест матрицы поворота"""
        angle = math.pi / 4  # 45 градусов
        pose = Pose2(ang=angle)
        R = pose.rotation_matrix()
        R_arr = np.asarray(R)
        
        # Проверка размера
        self.assertEqual(R_arr.shape, (2, 2))
        
        # Проверка значений для 45 градусов
        c = math.cos(angle)
        s = math.sin(angle)
        expected = np.array([[c, -s], [s, c]])
        np.testing.assert_array_almost_equal(R_arr, expected)

    def test_transform_point(self):
        """Тест трансформации точки"""
        # Поворот на 90 градусов против часовой стрелки + сдвиг на (1, 2)
        pose = Pose2(ang=math.pi/2, lin=np.array([1.0, 2.0]))
        
        # Точка (1, 0) после поворота на 90° становится (0, 1), потом сдвиг -> (1, 3)
        point = np.array([1.0, 0.0])
        transformed = pose.transform_point(point)
        
        expected = np.array([1.0, 3.0])
        np.testing.assert_array_almost_equal(list(transformed), expected)

    def test_transform_vector(self):
        """Тест трансформации вектора (без сдвига)"""
        # Поворот на 90 градусов + сдвиг (сдвиг не должен влиять на вектор)
        pose = Pose2(ang=math.pi/2, lin=np.array([1.0, 2.0]))
        
        # Вектор (1, 0) после поворота на 90° становится (0, 1)
        vector = np.array([1.0, 0.0])
        transformed = pose.transform_vector(vector)
        
        expected = np.array([0.0, 1.0])
        np.testing.assert_array_almost_equal(list(transformed), expected)

    def test_inverse(self):
        """Тест инверсии позы"""
        pose = Pose2(ang=math.pi/4, lin=np.array([1.0, 2.0]))
        inv_pose = pose.inverse()
        
        # Композиция позы с её инверсией должна дать единичную позу
        identity = pose * inv_pose
        
        self.assertAlmostEqual(identity.ang, 0.0, places=10)
        np.testing.assert_array_almost_equal(list(identity.lin), np.array([0.0, 0.0]))

    def test_composition(self):
        """Тест композиции поз"""
        # Первая поза: поворот на 45° + сдвиг на (1, 0)
        pose1 = Pose2(ang=math.pi/4, lin=np.array([1.0, 0.0]))
        
        # Вторая поза: поворот на 45° + сдвиг на (0, 1)
        pose2 = Pose2(ang=math.pi/4, lin=np.array([0.0, 1.0]))
        
        # Композиция
        composed = pose1 * pose2
        
        # Угол должен быть суммой углов
        expected_ang = math.pi/2
        self.assertAlmostEqual(composed.ang, expected_ang)
        
        # Проверка трансформации точки
        point = np.array([1.0, 0.0])
        
        # Применяем композицию
        p_composed = composed.transform_point(point)
        
        # Применяем последовательно
        p_temp = pose2.transform_point(point)
        p_sequential = pose1.transform_point(p_temp)
        
        np.testing.assert_array_almost_equal(list(p_composed), list(p_sequential))

    def test_translation(self):
        """Тест создания позы с только сдвигом"""
        pose = Pose2.translation(3.0, 4.0)
        
        self.assertEqual(pose.ang, 0.0)
        np.testing.assert_array_equal(list(pose.lin), np.array([3.0, 4.0]))
        
        # Проверка трансформации точки
        point = np.array([1.0, 2.0])
        transformed = pose.transform_point(point)
        np.testing.assert_array_equal(list(transformed), np.array([4.0, 6.0]))

    def test_rotation(self):
        """Тест создания позы с только поворотом"""
        angle = math.pi / 3  # 60 градусов
        pose = Pose2.rotation(angle)
        
        self.assertEqual(pose.ang, angle)
        np.testing.assert_array_equal(list(pose.lin), np.array([0.0, 0.0]))

    def test_as_matrix(self):
        """Тест получения матрицы трансформации 3x3"""
        pose = Pose2(ang=math.pi/2, lin=np.array([1.0, 2.0]))
        mat = pose.as_matrix()
        mat_arr = np.asarray(mat)
        
        # Проверка размера
        self.assertEqual(mat_arr.shape, (3, 3))
        
        # Проверка структуры матрицы
        # [R | t]
        # [0 | 1]
        R = np.asarray(pose.rotation_matrix())
        np.testing.assert_array_almost_equal(mat_arr[:2, :2], R)
        np.testing.assert_array_almost_equal(mat_arr[:2, 2], list(pose.lin))
        np.testing.assert_array_almost_equal(mat_arr[2, :], np.array([0.0, 0.0, 1.0]))

    def test_inverse_transform_point(self):
        """Тест обратной трансформации точки"""
        pose = Pose2(ang=math.pi/4, lin=np.array([1.0, 2.0]))
        
        # Прямая и обратная трансформация должны компенсировать друг друга
        original = np.array([3.0, 4.0])
        transformed = pose.transform_point(original)
        restored = pose.inverse_transform_point(transformed)
        
        np.testing.assert_array_almost_equal(list(restored), original)

    def test_lerp(self):
        """Тест линейной интерполяции"""
        pose1 = Pose2(ang=0.0, lin=np.array([0.0, 0.0]))
        pose2 = Pose2(ang=math.pi/2, lin=np.array([2.0, 4.0]))
        
        # Интерполяция в середине
        mid = Pose2.lerp(pose1, pose2, 0.5)
        
        self.assertAlmostEqual(mid.ang, math.pi/4)
        np.testing.assert_array_almost_equal(list(mid.lin), np.array([1.0, 2.0]))
        
        # Интерполяция в начале
        start = Pose2.lerp(pose1, pose2, 0.0)
        self.assertAlmostEqual(start.ang, pose1.ang)
        np.testing.assert_array_almost_equal(list(start.lin), list(pose1.lin))
        
        # Интерполяция в конце
        end = Pose2.lerp(pose1, pose2, 1.0)
        self.assertAlmostEqual(end.ang, pose2.ang)
        np.testing.assert_array_almost_equal(list(end.lin), list(pose2.lin))

    def test_properties(self):
        """Тест свойств x и y"""
        pose = Pose2(lin=np.array([3.0, 4.0]))
        
        self.assertEqual(pose.x, 3.0)
        self.assertEqual(pose.y, 4.0)
        
        # Изменение через свойства
        pose.x = 5.0
        pose.y = 6.0
        
        np.testing.assert_array_equal(list(pose.lin), np.array([5.0, 6.0]))

    def test_normalize_angle(self):
        """Тест нормализации угла"""
        # Угол больше π
        pose = Pose2(ang=3 * math.pi)
        pose.normalize_angle()
        
        # Должен быть нормализован к [-π, π]
        self.assertGreaterEqual(pose.ang, -math.pi)
        self.assertLessEqual(pose.ang, math.pi)
        # 3π нормализуется к π (или -π, они эквивалентны)
        self.assertAlmostEqual(abs(pose.ang), math.pi, places=10)

    def test_moveX_moveY(self):
        """Тест вспомогательных методов перемещения"""
        pose_x = Pose2.moveX(3.0)
        np.testing.assert_array_equal(list(pose_x.lin), np.array([3.0, 0.0]))
        
        pose_y = Pose2.moveY(4.0)
        np.testing.assert_array_equal(list(pose_y.lin), np.array([0.0, 4.0]))
        
        pose_right = Pose2.right(2.0)
        np.testing.assert_array_equal(list(pose_right.lin), np.array([2.0, 0.0]))
        
        pose_forward = Pose2.forward(5.0)
        np.testing.assert_array_equal(list(pose_forward.lin), np.array([0.0, 5.0]))
