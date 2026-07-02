from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    Hotspot = apps.get_model("location", "Hotspot")

    for hotspot in Hotspot.objects.select_related("village__parent").all():
        if hotspot.village_id and hotspot.village.parent_id:
            hotspot.micro_catchment_id = hotspot.village.parent_id
            hotspot.save(update_fields=["micro_catchment"])
            hotspot.villages.add(hotspot.village_id)


def backwards(apps, schema_editor):
    Hotspot = apps.get_model("location", "Hotspot")

    for hotspot in Hotspot.objects.all():
        hotspot.villages.clear()
        hotspot.micro_catchment_id = None
        hotspot.save(update_fields=["micro_catchment"])


class Migration(migrations.Migration):

    dependencies = [
        ("location", "0022_hotspot_json_ext"),
    ]

    operations = [
        migrations.AddField(
            model_name="hotspot",
            name="micro_catchment",
            field=models.ForeignKey(
                blank=True,
                db_column="MicroCatchmentId",
                limit_choices_to={"type": "W"},
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="micro_catchment_hotspots",
                to="location.location",
            ),
        ),
        migrations.AddField(
            model_name="hotspot",
            name="villages",
            field=models.ManyToManyField(
                blank=True,
                db_table="tblHotspotVillages",
                related_name="hotspots",
                to="location.location",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
