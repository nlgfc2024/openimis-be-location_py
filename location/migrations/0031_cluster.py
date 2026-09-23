import datetime
import uuid

import core.fields
import core.utils
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("location", "0030_merge_0028_unique_active_micro_catchment_code_0029_add_catchment_rights"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cluster",
            fields=[
                ("validity_from", core.fields.DateTimeField(db_column="ValidityFrom", default=datetime.datetime.now)),
                ("validity_to", core.fields.DateTimeField(blank=True, db_column="ValidityTo", null=True)),
                ("legacy_id", models.IntegerField(blank=True, db_column="LegacyID", null=True)),
                ("id", models.AutoField(db_column="ClusterId", primary_key=True, serialize=False)),
                ("uuid", models.CharField(db_column="ClusterUUID", default=uuid.uuid4, max_length=36, unique=True)),
                ("code", models.CharField(db_column="Code", max_length=50)),
                ("name", models.CharField(db_column="Name", max_length=255)),
                ("audit_user_id", models.IntegerField(db_column="AuditUserID")),
                ("traditional_authority", models.ForeignKey(db_column="TraditionalAuthorityId", limit_choices_to={"type": "D"}, on_delete=django.db.models.deletion.PROTECT, related_name="clusters", to="location.location")),
            ],
            options={"db_table": "tblClusters", "managed": True},
            bases=(core.utils.CachedModelMixin, models.Model),
        ),
    ]
