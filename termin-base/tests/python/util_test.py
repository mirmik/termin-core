import unittest
from termin.geombase import Quat, qslerp
import numpy
import math

class TestUtil(unittest.TestCase):
    def test_slerp(self):
        q1 = Quat(0.0, 0.0, math.sin(0.0), math.cos(0.0))  # Identity quaternion
        q2 = Quat(0.0, 0.0, math.sin(math.pi/2), math.cos(math.pi/2))  # 90 degrees around Z

        q_halfway = qslerp(q1, q2, 0.5)
        expected_halfway = numpy.array([0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)])

        numpy.testing.assert_array_almost_equal(q_halfway.tolist(), expected_halfway)
