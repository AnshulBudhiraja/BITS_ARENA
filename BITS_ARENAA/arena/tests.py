from django.test import TestCase

class SanityCheckTest(TestCase):
    def test_environment_is_working(self):
        # If Django is running correctly, 1 + 1 will equal 2
        self.assertEqual(1 + 1, 2)
