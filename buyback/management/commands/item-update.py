# buyback/management/commands/update_items.py
import time
import logging
import requests

from django.core.management.base import BaseCommand
from buyback.models import EveItemTax

# Configure logging for the command
logger = logging.getLogger(__name__)

# ESI API base URL
ESI_BASE = "https://esi.evetech.net/latest"

class Command(BaseCommand):
    help = "Check EveItemTax for missing or outdated info and repair via ESI"

    def fetch_type_data(self, type_id):
        """Fetch the type data from ESI /universe/types/{type_id}/"""
        url = f"{ESI_BASE}/universe/types/{type_id}/"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning("Failed to fetch type data for %s: %s", type_id, e)
            return None

    def fetch_group_data(self, group_id):
        """Fetch the group data from ESI /universe/groups/{group_id}/"""
        url = f"{ESI_BASE}/universe/groups/{group_id}/"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning("Failed to fetch group data for %s: %s", group_id, e)
            return None

    def fetch_category_data(self, category_id):
        """Fetch the category data from ESI /universe/categories/{category_id}/"""
        url = f"{ESI_BASE}/universe/categories/{category_id}/"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning("Failed to fetch category data for %s: %s", category_id, e)
            return None

    def repair_item(self, item: EveItemTax):
        """Repair a single item"""
        logger.info("Checking item %s (%s)", item.pk, item.type_name)

        type_data = self.fetch_type_data(item.type_id)
        if not type_data:
            logger.warning("No type data found for %s", item.type_name)
            return

        group_id = type_data.get("group_id", 0)
        group_name = ""
        category_id = 0
        category_name = ""

        if group_id:
            group_data = self.fetch_group_data(group_id)
            if group_data:
                group_name = group_data.get("name", "")
                category_id = group_data.get("category_id", 0)
                if category_id:
                    category_data = self.fetch_category_data(category_id)
                    if category_data:
                        category_name = category_data.get("name", "")

        # Log old vs new
        logger.info(
            "Item %s group updated: old_id=%s, new_id=%s, old_name=%s, new_name=%s",
            item.type_name, item.group_id, group_id, item.group, group_name
        )
        logger.info(
            "Item %s category updated: old_id=%s, new_id=%s, old_name=%s, new_name=%s",
            item.type_name, item.category_id, category_id, item.category_name, category_name
        )

        # Update item
        item.group_id = group_id
        item.group = group_name
        item.category_id = category_id
        item.category_name = category_name
        item.needs_update = False
        item.save()

        # Throttle requests to avoid getting banned
        time.sleep(0.5)

    def handle(self, *args, **options):
        # Query items that need an update
        items_to_update = EveItemTax.objects.filter(needs_update=True)
        logger.info("Found %d items to update", items_to_update.count())

        for item in items_to_update:
            self.repair_item(item)

        logger.info("Update complete.")
