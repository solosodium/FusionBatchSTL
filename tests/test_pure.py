"""Tests for the Fusion-independent modules. Run with: python -m unittest discover tests"""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'batchstl'))

import naming  # noqa: E402
import stl_writer  # noqa: E402

# Two meshes: a single triangle, and a second triangle offset in z.
TRI = ([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 2])
TRI2 = ([0, 0, 5, 1, 0, 5, 0, 1, 5], [0, 1, 2])


class StlWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_binary_merges_meshes(self):
        path = os.path.join(self.tmp.name, 'a.stl')
        n = stl_writer.write_stl(path, [TRI, TRI2], binary=True, solid_name='x')
        self.assertEqual(n, 2)
        with open(path, 'rb') as f:
            data = f.read()
        self.assertEqual(len(data), 84 + 50 * 2)
        self.assertFalse(data[:5].lower() == b'solid')
        self.assertEqual(struct.unpack('<I', data[80:84])[0], 2)
        facet = struct.unpack('<12fH', data[84:134])
        self.assertEqual(facet[:3], (0.0, 0.0, 1.0))  # normal of CCW triangle in XY plane
        facet2 = struct.unpack('<12fH', data[134:184])
        self.assertEqual(facet2[5], 5.0)

    def test_ascii(self):
        path = os.path.join(self.tmp.name, 'a.stl')
        stl_writer.write_stl(path, [TRI], binary=False, solid_name='my part')
        with open(path) as f:
            text = f.read()
        self.assertTrue(text.startswith('solid my_part\n'))
        self.assertEqual(text.count('facet normal'), 1)
        self.assertTrue(text.rstrip().endswith('endsolid my_part'))

    def test_degenerate_triangle_has_zero_normal(self):
        path = os.path.join(self.tmp.name, 'a.stl')
        stl_writer.write_stl(path, [([0, 0, 0, 1, 1, 1, 2, 2, 2], [0, 1, 2])])
        with open(path, 'rb') as f:
            f.seek(84)
            self.assertEqual(struct.unpack('<3f', f.read(12)), (0.0, 0.0, 0.0))


class NamingTests(unittest.TestCase):
    def test_render_subfolders_and_sanitize(self):
        out = naming.render('{document}/{body}', document='My: Part', body='Body/1')
        self.assertEqual(out, os.path.join('My_ Part', 'Body_1'))

    def test_empty_tokens_are_dropped(self):
        self.assertEqual(naming.render('{occurrence}/{body}', occurrence='', body='B'), 'B')
        self.assertEqual(naming.render('{document}_{occurrence}_{body}', document='D', occurrence='', body='B'),
                         'D_B')

    def test_unknown_token_kept_and_bad_template_tolerated(self):
        self.assertEqual(naming.render('{nope}_{body}', body='B'), '{nope}_B')
        self.assertEqual(naming.render('{body', body='B'), '{body')

    def test_no_parent_escape(self):
        self.assertEqual(naming.render('../{body}', body='B'), 'B')

    def test_reserved_names(self):
        self.assertEqual(naming.render('{body}', body='CON'), '_CON')

    def test_strip_version(self):
        self.assertEqual(naming.strip_version('Bracket v12'), 'Bracket')
        self.assertEqual(naming.strip_version('Bracket'), 'Bracket')

    def test_make_unique(self):
        self.assertEqual(naming.make_unique(['a', 'A', 'b', 'a', 'a_2']), ['a', 'A_2', 'b', 'a_3', 'a_2_2'])

    def test_avoid_existing(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x.stl')
            self.assertEqual(naming.avoid_existing(p), p)
            open(p, 'w').close()
            self.assertEqual(naming.avoid_existing(p), os.path.join(d, 'x (1).stl'))


if __name__ == '__main__':
    unittest.main()
