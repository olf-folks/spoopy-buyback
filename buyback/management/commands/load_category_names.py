# from django.core.management.base import BaseCommand
# from django.core.cache import cache
# import requests
# from buyback.models import EveItemTax

# class Command(BaseCommand):
#     help = 'Load group names and category information from the API and update the database'

#     def handle(self, *args, **options):
#         # Load all category IDs from the API
#         category_ids = [
#             0, 23, 46, 1, 24, 2, 25, 2118, 3, 26, 49, 4, 5, 6, 29, 7, 30, 2100, 53,
#             8, 54, 9, 32, 10, 350001, 11, 34, 35, 59, 14, 2107, 16, 39, 17, 40, 63,
#             18, 41, 87, 42, 65, 20, 43, 66, 22, 91
#         ]

#         for category_id in category_ids:
#             # Check if the category info is already cached
#             cached_category_info = cache.get(f'category_info_{category_id}')

#             if cached_category_info is None:
#                 # Fetch category info from API and cache it
#                 category_info = requests.get(f"https://esi.evetech.net/latest/universe/categories/{category_id}/?datasource=tranquility&language=en").json()
#                 cache.set(f'category_info_{category_id}', category_info)
#             else:
#                 category_info = cached_category_info

#             group_ids = category_info['groups']
#             category_name = category_info['name']

#             for group_id in group_ids:
#                 # Check if the group info is already cached
#                 cached_group_info = cache.get(f'group_info_{group_id}')

#                 if cached_group_info is None:
#                     # Fetch group info from API and cache it
#                     group_info = requests.get(f"https://esi.evetech.net/latest/universe/groups/{group_id}/").json()
#                     cache.set(f'group_info_{group_id}', group_info)
#                 else:
#                     group_info = cached_group_info

#                 group_name = group_info['name']
#                 EveItemTax.objects.filter(group_id=group_id).update(category_id=category_id, category_name=category_name)

#                 self.stdout.write(self.style.SUCCESS(f'Successfully updated category information for group ID {group_id}'))

#         self.stdout.write(self.style.SUCCESS('Finished updating category information'))



#v2

# from django.core.management.base import BaseCommand
# from django.core.cache import cache
# import requests
# from buyback.models import EveItemTax

# class Command(BaseCommand):
#     help = 'Load group names and category information from the API and update the database'

#     def handle(self, *args, **options):
#         # Load all category IDs from the API
#         category_ids = [
#             0, 23, 46, 1, 24, 2, 25, 2118, 3, 26, 49, 4, 5, 6, 29, 7, 30, 2100, 53,
#             8, 54, 9, 32, 10, 350001, 11, 34, 35, 59, 14, 2107, 16, 39, 17, 40, 63,
#             18, 41, 87, 42, 65, 20, 43, 66, 22, 91
#         ]

#         # Initialize a dictionary to cache category and group info
#         cached_data = {}

#         for category_id in category_ids:
#             # Check if category info is cached
#             if f'category_info_{category_id}' not in cached_data:
#                 # Fetch category info from API and cache it
#                 category_info = requests.get(f"https://esi.evetech.net/latest/universe/categories/{category_id}/?datasource=tranquility&language=en").json()
#                 cached_data[f'category_info_{category_id}'] = category_info

#             group_ids = cached_data[f'category_info_{category_id}']['groups']
#             category_name = cached_data[f'category_info_{category_id}']['name']

#             for group_id in group_ids:
#                 # Check if group info is cached
#                 if f'group_info_{group_id}' not in cached_data:
#                     # Fetch group info from API and cache it
#                     group_info = requests.get(f"https://esi.evetech.net/latest/universe/groups/{group_id}/").json()
#                     cached_data[f'group_info_{group_id}'] = group_info

#                 group_name = cached_data[f'group_info_{group_id}']['name']
#                 EveItemTax.objects.filter(group_id=group_id).update(category_id=category_id, category_name=category_name)

#                 self.stdout.write(self.style.SUCCESS(f'Successfully updated category information for group ID {group_id}'))

#         self.stdout.write(self.style.SUCCESS('Finished updating category information'))

#V3 - retry when not 200 resp


from django.core.management.base import BaseCommand
from django.core.cache import cache
import requests
from buyback.models import EveItemTax

class Command(BaseCommand):
    help = 'Load group names and category information from the API and update the database'

    def handle(self, *args, **options):
        # Load all category IDs from the API
        category_ids = [
            0, 23, 46, 1, 24, 2, 25, 2118, 3, 26, 49, 4, 5, 6, 29, 7, 30, 2100, 53,
            8, 54, 9, 32, 10, 350001, 11, 34, 35, 59, 14, 2107, 16, 39, 17, 40, 63,
            18, 41, 87, 42, 65, 20, 43, 66, 22, 91
        ]

        for category_id in category_ids:
            attempts = 3  # Number of retry attempts
            while attempts > 0:
                # Fetch category info from API and cache it
                response = requests.get(f"https://esi.evetech.net/latest/universe/categories/{category_id}/?datasource=tranquility&language=en")

                if response.status_code == 200:
                    category_info = response.json()
                    cache.set(f'category_info_{category_id}', category_info)
                    break  # Successful response, break out of the loop
                else:
                    attempts -= 1
                    self.stdout.write(self.style.WARNING(f'Failed to fetch category info for ID {category_id}. Retrying...'))

            if attempts == 0:
                self.stdout.write(self.style.ERROR(f'Failed to fetch category info for ID {category_id} after retries'))

            # ... Rest of the code to update group info using cached category info ...

            for category_id in category_ids:
                attempts = 3  # Number of retry attempts
                while attempts > 0:
                    # Fetch category info from API and cache it
                    response = requests.get(f"https://esi.evetech.net/latest/universe/categories/{category_id}/?datasource=tranquility&language=en")

                    if response.status_code == 200:
                        category_info = response.json()
                        cache.set(f'category_info_{category_id}', category_info)
                        break  # Successful response, break out of the loop
                    else:
                        attempts -= 1
                        self.stdout.write(self.style.WARNING(f'Failed to fetch category info for ID {category_id}. Retrying...'))

                if attempts == 0:
                    self.stdout.write(self.style.ERROR(f'Failed to fetch category info for ID {category_id} after retries'))

                # Fetch group IDs from cached category info
                group_ids = category_info['groups']
                category_name = category_info['name']

                # Iterate through the group IDs
                for group_id in group_ids:
                    attempts = 3  # Number of retry attempts
                    while attempts > 0:
                        # Fetch group info from API and cache it
                        response = requests.get(f"https://esi.evetech.net/latest/universe/groups/{group_id}/")

                        if response.status_code == 200:
                            group_info = response.json()
                            cache.set(f'group_info_{group_id}', group_info)
                            break  # Successful response, break out of the loop
                        else:
                            attempts -= 1
                            self.stdout.write(self.style.WARNING(f'Failed to fetch group info for ID {group_id}. Retrying...'))

                    if attempts == 0:
                        self.stdout.write(self.style.ERROR(f'Failed to fetch group info for ID {group_id} after retries'))

                    group_name = group_info['name']
                    # Update the database with category and group info
                    EveItemTax.objects.filter(group_id=group_id).update(category_id=category_id, category_name=category_name)

                    self.stdout.write(self.style.SUCCESS(f'Successfully updated category and group information for group ID {group_id}'))

            self.stdout.write(self.style.SUCCESS('Finished updating category and group information'))
