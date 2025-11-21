from django.test import SimpleTestCase
from buyback.templatetags.custom_filters import low, add_commas

class TestCustomFilters(SimpleTestCase):
    def test_low(self):
        self.assertEqual(low("HELLO"), "hello")
        self.assertEqual(low("World"), "world")
        self.assertEqual(low(""), "")

    def test_add_commas_integer(self):
        self.assertEqual(add_commas(1000), "1,000")
        self.assertEqual(add_commas(1000000), "1,000,000")
        self.assertEqual(add_commas(0), "0")

    def test_add_commas_string_integer(self):
        self.assertEqual(add_commas("1000"), "1,000")

    def test_add_commas_invalid(self):
        self.assertEqual(add_commas("invalid"), "invalid")
        self.assertEqual(add_commas(None), None)

