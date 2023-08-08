import requests

def get_group_name_from_api(group_id):
    url = f"https://esi.evetech.net/latest/universe/groups/{group_id}/?datasource=tranquility&language=en"
    response = requests.get(url)
    if response.status_code == 200:
        group_data = response.json()
        return group_data.get("name", f"Group {group_id}")
    else:
        return f"Group {group_id}"


