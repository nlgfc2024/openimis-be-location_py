from django.db import migrations, models
import django.db.models.deletion


def rename_zone_tables(apps, schema_editor):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    cursor = schema_editor.connection.cursor()

    if connection.vendor == "postgresql":
        cursor.execute(f'ALTER TABLE {quote("tblHotspots")} RENAME TO {quote("tblZones")}')
        cursor.execute(f'ALTER TABLE {quote("tblHotspotVillages")} RENAME TO {quote("tblZoneVillages")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("HotspotId")} TO {quote("ZoneId")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("HotspotUUID")} TO {quote("ZoneUUID")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("HotspotCode")} TO {quote("ZoneCode")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("HotspotName")} TO {quote("ZoneName")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("HotspotDescription")} TO {quote("ZoneDescription")}')
        cursor.execute(f'ALTER TABLE {quote("tblZoneVillages")} RENAME COLUMN {quote("HotspotVillageId")} TO {quote("ZoneVillageId")}')
        cursor.execute(f'ALTER TABLE {quote("tblZoneVillages")} RENAME COLUMN {quote("HotspotId")} TO {quote("ZoneId")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} ADD COLUMN {quote("ClusterId")} integer NULL')
    else:
        cursor.execute("EXEC sp_rename 'tblHotspots', 'tblZones'")
        cursor.execute("EXEC sp_rename 'tblHotspotVillages', 'tblZoneVillages'")
        for table, old, new in (
            ("tblZones", "HotspotId", "ZoneId"),
            ("tblZones", "HotspotUUID", "ZoneUUID"),
            ("tblZones", "HotspotCode", "ZoneCode"),
            ("tblZones", "HotspotName", "ZoneName"),
            ("tblZones", "HotspotDescription", "ZoneDescription"),
            ("tblZoneVillages", "HotspotVillageId", "ZoneVillageId"),
            ("tblZoneVillages", "HotspotId", "ZoneId"),
        ):
            cursor.execute(f"EXEC sp_rename '{table}.{old}', '{new}', 'COLUMN'")
        cursor.execute('ALTER TABLE "tblZones" ADD "ClusterId" integer NULL')


def restore_hotspot_tables(apps, schema_editor):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    cursor = schema_editor.connection.cursor()

    if connection.vendor == "postgresql":
        cursor.execute(f'ALTER TABLE {quote("tblZones")} DROP COLUMN {quote("ClusterId")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("ZoneId")} TO {quote("HotspotId")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("ZoneUUID")} TO {quote("HotspotUUID")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("ZoneCode")} TO {quote("HotspotCode")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("ZoneName")} TO {quote("HotspotName")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME COLUMN {quote("ZoneDescription")} TO {quote("HotspotDescription")}')
        cursor.execute(f'ALTER TABLE {quote("tblZoneVillages")} RENAME COLUMN {quote("ZoneVillageId")} TO {quote("HotspotVillageId")}')
        cursor.execute(f'ALTER TABLE {quote("tblZoneVillages")} RENAME COLUMN {quote("ZoneId")} TO {quote("HotspotId")}')
        cursor.execute(f'ALTER TABLE {quote("tblZoneVillages")} RENAME TO {quote("tblHotspotVillages")}')
        cursor.execute(f'ALTER TABLE {quote("tblZones")} RENAME TO {quote("tblHotspots")}')
    else:
        cursor.execute('ALTER TABLE "tblZones" DROP COLUMN "ClusterId"')
        for table, old, new in (
            ("tblZones", "ZoneId", "HotspotId"),
            ("tblZones", "ZoneUUID", "HotspotUUID"),
            ("tblZones", "ZoneCode", "HotspotCode"),
            ("tblZones", "ZoneName", "HotspotName"),
            ("tblZones", "ZoneDescription", "HotspotDescription"),
            ("tblZoneVillages", "ZoneVillageId", "HotspotVillageId"),
            ("tblZoneVillages", "ZoneId", "HotspotId"),
        ):
            cursor.execute(f"EXEC sp_rename '{table}.{old}', '{new}', 'COLUMN'")
        cursor.execute("EXEC sp_rename 'tblZoneVillages', 'tblHotspotVillages'")
        cursor.execute("EXEC sp_rename 'tblZones', 'tblHotspots'")


class Migration(migrations.Migration):
    dependencies = [("location", "0032_register_cluster_menu")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(rename_zone_tables, restore_hotspot_tables)],
            state_operations=[
                migrations.RenameModel("Hotspot", "Zone"),
                migrations.RenameModel("HotspotVillage", "ZoneVillage"),
                migrations.AlterModelTable("zone", "tblZones"),
                migrations.AlterModelTable("zonevillage", "tblZoneVillages"),
                migrations.AlterField("zone", "id", models.AutoField(db_column="ZoneId", primary_key=True, serialize=False)),
                migrations.AlterField("zone", "uuid", models.CharField(db_column="ZoneUUID", max_length=36, unique=True)),
                migrations.AlterField("zone", "code", models.CharField(db_column="ZoneCode", max_length=50, unique=True)),
                migrations.AlterField("zone", "name", models.CharField(db_column="ZoneName", max_length=100)),
                migrations.AlterField("zone", "description", models.TextField(blank=True, db_column="ZoneDescription", null=True)),
                migrations.AddField(
                    model_name="zone",
                    name="cluster",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="ClusterId",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="zones",
                        to="location.cluster",
                    ),
                ),
                migrations.AlterField(
                    "zone",
                    "micro_catchment",
                    models.ForeignKey(
                        blank=True,
                        db_column="MicroCatchmentId",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="legacy_zones",
                        to="location.microcatchment",
                    ),
                ),
                migrations.RenameField("zonevillage", "hotspot", "zone"),
                migrations.AlterField("zonevillage", "id", models.AutoField(db_column="ZoneVillageId", primary_key=True, serialize=False)),
                migrations.AlterField("zonevillage", "zone", models.ForeignKey(db_column="ZoneId", on_delete=django.db.models.deletion.CASCADE, related_name="village_links", to="location.zone")),
                migrations.AlterField("zonevillage", "location", models.ForeignKey(db_column="LocationId", limit_choices_to={"type": "V"}, on_delete=django.db.models.deletion.CASCADE, related_name="zone_links", to="location.location")),
            ],
        ),
        # Keep the old model name available for modules that still reference Hotspot.
        migrations.CreateModel(
            name="Hotspot",
            fields=[],
            options={"proxy": True, "indexes": [], "constraints": []},
            bases=("location.zone",),
        ),
    ]
