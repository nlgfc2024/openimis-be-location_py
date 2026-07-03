import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("location", "0019_alter_location_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="MicroCatchment",
            fields=[
                ("id", models.AutoField(db_column="MicroCatchmentId", primary_key=True, serialize=False)),
                ("uuid", models.CharField(db_column="MicroCatchmentUUID", default=uuid.uuid4, max_length=36, unique=True)),
                ("code", models.CharField(db_column="Code", max_length=50)),
                ("name", models.CharField(db_column="Name", max_length=255)),
                ("type", models.CharField(blank=True, db_column="Type", max_length=50, null=True)),
                ("date_from", models.DateField(blank=True, db_column="DateFrom", null=True)),
                ("date_to", models.DateField(blank=True, db_column="DateTo", null=True)),
                ("max_beneficiaries", models.IntegerField(blank=True, db_column="MaxBeneficiaries", null=True)),
                ("audit_user_id", models.IntegerField(db_column="AuditUserID")),
                ("validity_from", models.DateTimeField(blank=True, db_column="ValidityFrom", null=True)),
                ("validity_to", models.DateTimeField(blank=True, db_column="ValidityTo", null=True)),
                ("legacy_id", models.IntegerField(blank=True, db_column="LegacyId", null=True)),
                (
                    "district",
                    models.ForeignKey(
                        blank=True,
                        db_column="DistrictId",
                        limit_choices_to={"type": "D"},
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="micro_catchments",
                        to="location.location",
                    ),
                ),
            ],
            options={
                "db_table": "tblMicroCatchments",
                "managed": True,
            },
        ),
        migrations.CreateModel(
            name="MicroCatchmentTA",
            fields=[
                ("id", models.AutoField(db_column="MicroCatchmentTAId", primary_key=True, serialize=False)),
                ("audit_user_id", models.IntegerField(db_column="AuditUserID")),
                ("validity_from", models.DateTimeField(blank=True, db_column="ValidityFrom", null=True)),
                ("validity_to", models.DateTimeField(blank=True, db_column="ValidityTo", null=True)),
                ("legacy_id", models.IntegerField(blank=True, db_column="LegacyId", null=True)),
                (
                    "micro_catchment",
                    models.ForeignKey(
                        db_column="MicroCatchmentId",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="traditional_authorities",
                        to="location.microcatchment",
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        db_column="LocationId",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="micro_catchments_ta",
                        to="location.location",
                    ),
                ),
            ],
            options={
                "db_table": "tblMicroCatchmentTA",
                "managed": True,
            },
        ),
        migrations.CreateModel(
            name="MicroCatchmentGVH",
            fields=[
                ("id", models.AutoField(db_column="MicroCatchmentGVHId", primary_key=True, serialize=False)),
                ("audit_user_id", models.IntegerField(db_column="AuditUserID")),
                ("validity_from", models.DateTimeField(blank=True, db_column="ValidityFrom", null=True)),
                ("validity_to", models.DateTimeField(blank=True, db_column="ValidityTo", null=True)),
                ("legacy_id", models.IntegerField(blank=True, db_column="LegacyId", null=True)),
                (
                    "micro_catchment",
                    models.ForeignKey(
                        db_column="MicroCatchmentId",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gvhs",
                        to="location.microcatchment",
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        db_column="LocationId",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="micro_catchments_gvh",
                        to="location.location",
                    ),
                ),
            ],
            options={
                "db_table": "tblMicroCatchmentGVH",
                "managed": True,
            },
        ),
    ]
