import json

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import ModuleConfiguration, Role, RoleRight, UserRole
from core.utils import TimeUtils
from location.jobs_now_configuration import LOCATION_RIGHTS, add_jobs_now_menus


class Command(BaseCommand):
    help = "Preview or apply Jobs-Now location menus and optionally grant location rights to a role."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the previewed configuration changes.")
        parser.add_argument("--role-id", type=int, help="Optional active role receiving Cluster, Zone and Hotspot rights.")

    @transaction.atomic
    def handle(self, *args, **options):
        role = None
        if options["role_id"] is not None:
            role = Role.objects.filter(pk=options["role_id"], validity_to__isnull=True).first()
            if role is None:
                raise CommandError("Select an existing active role ID.")
        for row in ModuleConfiguration.objects.filter(layer="fe", module="fe-core"):
            config = json.loads(row.config or "{}")
            if add_jobs_now_menus(config):
                self.stdout.write(f"Add Cluster/Zone menu entries to configuration {row.pk}.")
                if options["apply"]:
                    row.config = json.dumps(config)
                    row.save(update_fields=["config"])
        if role:
            for right_id in (right for rights in LOCATION_RIGHTS.values() for right in rights):
                if not RoleRight.objects.filter(role=role, right_id=right_id, validity_to__isnull=True).exists():
                    self.stdout.write(f"Grant right {right_id} to role {role.pk}.")
                    if options["apply"]:
                        RoleRight.objects.create(role=role, right_id=right_id, validity_from=TimeUtils.now())
            if options["apply"]:
                keys = ["rights_" + str(user_id) for user_id in UserRole.objects.filter(
                    role=role, validity_to__isnull=True,
                ).values_list("user_id", flat=True)]
                transaction.on_commit(lambda: cache.delete_many(keys))
        self.stdout.write("Applied. Sign in again to refresh permissions." if options["apply"] else "Preview only. Repeat with --apply to save.")
