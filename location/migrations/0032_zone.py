import datetime
import uuid

import core.fields
import core.utils
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("location", "0031_cluster")]

    operations = [
        migrations.CreateModel(
            name="Zone",
            fields=[
                ("validity_from", core.fields.DateTimeField(db_column="ValidityFrom", default=datetime.datetime.now)),
                ("validity_to", core.fields.DateTimeField(blank=True, db_column="ValidityTo", null=True)),
                ("legacy_id", models.IntegerField(blank=True, db_column="LegacyID", null=True)),
                ("json_ext", models.JSONField(blank=True, db_column="JsonExt", null=True)),
                ("id", models.AutoField(db_column="ZoneId", primary_key=True, serialize=False)),
                ("uuid", models.CharField(db_column="ZoneUUID", default=uuid.uuid4, max_length=36, unique=True)),
                ("code", models.CharField(db_column="ZoneCode", max_length=50, unique=True)),
                ("name", models.CharField(db_column="ZoneName", max_length=100)),
                ("description", models.TextField(blank=True, db_column="ZoneDescription", null=True)),
                ("audit_user_id", models.IntegerField(blank=True, db_column="AuditUserID", null=True)),
                ("cluster", models.ForeignKey(blank=True, db_column="ClusterId", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="zones", to="location.cluster")),
            ],
            options={"db_table": "tblZones", "managed": True},
            bases=(core.utils.CachedModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name="ZoneVillage",
            fields=[
                ("validity_from", core.fields.DateTimeField(db_column="ValidityFrom", default=datetime.datetime.now)),
                ("validity_to", core.fields.DateTimeField(blank=True, db_column="ValidityTo", null=True)),
                ("legacy_id", models.IntegerField(blank=True, db_column="LegacyID", null=True)),
                ("id", models.AutoField(db_column="ZoneVillageId", primary_key=True, serialize=False)),
                ("audit_user_id", models.IntegerField(blank=True, db_column="AuditUserID", null=True)),
                ("zone", models.ForeignKey(db_column="ZoneId", on_delete=django.db.models.deletion.CASCADE, related_name="village_links", to="location.zone")),
                ("location", models.ForeignKey(db_column="LocationId", limit_choices_to={"type": "V"}, on_delete=django.db.models.deletion.CASCADE, related_name="zone_links", to="location.location")),
            ],
            options={"db_table": "tblZoneVillages", "managed": True},
            bases=(core.utils.CachedModelMixin, models.Model),
        ),
    ]
