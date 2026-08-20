from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("location", "0027_remove_hotspot_villages_hotspotvillage"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="microcatchment",
            constraint=models.UniqueConstraint(
                fields=("code",),
                condition=Q(validity_to__isnull=True),
                name="unique_active_micro_catchment_code",
            ),
        ),
    ]
