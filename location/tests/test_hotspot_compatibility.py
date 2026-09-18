from django.test import SimpleTestCase


class HotspotCompatibilityTest(SimpleTestCase):
    def test_hotspot_model_name_is_available(self):
        from location.models import Hotspot, Zone
        self.assertTrue(issubclass(Hotspot, Zone))
        self.assertTrue(Hotspot._meta.proxy)
        self.assertEqual(Hotspot._meta.concrete_model, Zone)
