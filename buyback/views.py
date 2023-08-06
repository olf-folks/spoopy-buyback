# Create your views here.
from django.http import Http404
import requests
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.shortcuts import render, redirect
from import_export.formats import base_formats
# from .forms import ImportForm
from .forms import ItemForm
import pandas as pd
import re
from .models import EveItemTax  # Import your model

import logging

logger = logging.getLogger(__name__)

re_asset_list = re.compile(r'^([\S ]+)\s+([\d,]+)$')


## works only with game pasted input
# def parse_user_input(form_data):
#     parsed_input = []
#     logger.debug("form_data input in into parse user input function: %s", form_data)
#     items_list = re.split(r'\r?\n', form_data)  # Split using \r\n or \n as the delimiter
#     logger.debug("items_list in parse user input function: %s", items_list)
    
#     for item_input in items_list:
#         initial_string = item_input
#         #name = re.search(r'^(\S+)', initial_string).group(1)            
#         name = re.search(r'^([\S\ ]*)', initial_string).group(1)
#         # quantity = re.search(r"\t(\d+(?:,\d{3})*(?:\.\d+)?)|(?! |\t)(\d+)", initial_string)
#         quantity = re.search(r"\t(\d+(?:,\d{3})*(?:\.\d+)?)\s", initial_string)
#         if quantity:
#             quantity_str = quantity.group(1) or quantity.group(2)
#             quantity = int(quantity_str.replace(',', ''))
#         else:
#             quantity = 1

#         logger.debug("regex debug search found name: %s", name)
#         logger.debug("regex debug search found quantity: %s", quantity)
        
#         parsed_input.append({
#             'name': name,
#             'quantity': quantity,
#         })

#     return parsed_input


def parse_user_input(form_data):
    parsed_input = []
    logger.debug("form_data input in into parse user input function: %s", form_data)
    items_list = re.split(r'\r?\n', form_data)  # Split using \r\n or \n as the delimiter
    logger.debug("items_list in parse user input function: %s", items_list)
    
    for item_input in items_list:
        # Split the input by whitespace to separate name and quantity
        parts = item_input.strip().split()
        if len(parts) == 2:
            name = parts[0]
            quantity = parts[1]

            # Check if quantity is a valid integer
            if quantity.isdigit():
                quantity = int(quantity)
            else:
                quantity = 1

            logger.debug("found name: %s", name)
            logger.debug("found quantity: %s", quantity)
            
            parsed_input.append({
                'name': name,
                'quantity': quantity,
            })
        else:
            initial_string = item_input
            name = re.search(r'^([\S\ ]*)', initial_string).group(1)
            quantity = re.search(r"\t(\d+(?:,\d{3})*(?:\.\d+)?)|(?! |\t)(\d+)", initial_string)
            if quantity:
                quantity_str = quantity.group(1) or quantity.group(2)
                quantity = int(quantity_str.replace(',', ''))
            else:
                quantity = 1

            logger.debug("regex debug search found name: %s", name)
            logger.debug("regex debug search found quantity: %s", quantity)
            
            parsed_input.append({
                'name': name,
                'quantity': quantity,
            })

    return parsed_input


def calculate_buyback_price(item_price, tax_rate):
    buyback_price = item_price * tax_rate
    return buyback_price

def get_tax_rate_from_database(item_id):
    try:
        tax_entry = EveItemTax.objects.get(type_id=item_id)
        # return tax_entry.jita_buy_percentage / 100.0  # Convert percentage to decimal
        return tax_entry.jita_buy_percentage  # dont Convert percentage to decimal
    except EveItemTax.DoesNotExist:
        return 0.0  # Default tax rate if item not found

def get_haul_fee_bool_from_database(item_id):
    try:
        haul_fee_entry = EveItemTax.objects.get(type_id=item_id)
        # return tax_entry.jita_buy_percentage / 100.0  # Convert percentage to decimal
        return haul_fee_entry.hauling_fee  
    except EveItemTax.DoesNotExist:
        return False # Default to False not found
        

# def generate_api_input(parsed_user_input):
#     string = ""
#     for items in parsed_user_input:
#         name = items[0]   # Access the first item
#         quanity = items[1]  # Access the second item
#         space = " "
#         ret = "\n"
#         string = string+name+space+str(quanity)+ret
#         return string

def getqtys(parsed_user_input):
    qtys = [] 
    for item in parsed_user_input:
        quantity = item['quantity']
        qtys.append(quantity)

    return qtys  # Move the return statement outside the loop

def generate_api_input(parsed_user_input):
    string = ""
    for item in parsed_user_input:
        name = item['name']
        quantity = item['quantity']
        space = " "
        ret = "\n"
        string = string + name + space + str(quantity) + ret
    return string  # Move the return statement outside the loop

def index(request):
    haul_fee_rate_sv = 200 # set value is 200 ISK per m3
    debug = []
    info_right = 2
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            raw_user_input = form.cleaned_data['item_name']  # Get the input text from the form
            parsed_user_input = parse_user_input(raw_user_input)
            logger.debug("parsed_user_input: %s", parsed_user_input)
            api_input = generate_api_input(parsed_user_input)
            quantity = getqtys(parsed_user_input)
            logger.debug("apiinput: %s", api_input)
            janiceurl = 'https://janice.e-351.com/api/rest/v2/pricer?market=2'
            janiceheaders = {"accept": "application/json", "X-ApiKey": "G9KwKq3465588VPd6747t95Zh94q3W2E", "Content-Type": "text/plain"}
            janiceresponse = requests.post(janiceurl, api_input, headers=janiceheaders)
            api_data = janiceresponse.json()
            logger.debug("api_data: %s", api_data)

            # make list of dicts that combines api_data + tax_rate + api_input \\ need to add: hauling fee ###
            processed_items = []
            for item in parsed_user_input:
                
                item_name = item['name']
                item_name_lower = item_name.lower()
                quantity = item['quantity']
                #item_id = api_data[0]['itemType']['eid']  # Assuming you get the item ID from the API response
                #item_data = next((item for item in api_data if item['itemType']['name'] == item_name), None)
                #item_data = next((item for item in api_data if item['itemType']['name'] == item['name']), None)
                #item_data = next((item for item in api_data if item['itemType']['name'] == item_data['itemType']['name']), None)
                # item_data = next((api_item for api_item in api_data if api_item['itemType']['name'] == item_name), None)
                item_data = next((api_item for api_item in api_data if api_item['itemType']['name'].lower() == item_name_lower), None)
            
                if item_data:
                    
                    item_id = item_data['itemType']['eid']
                    item_volume = item_data['itemType']['volume']                    
                    haul_bool = get_haul_fee_bool_from_database(item_id)
                    logger.debug("Is fee for haul?: %s", haul_bool)
                    if haul_bool == True:
                        total_item_vol = item_volume * quantity
                        haul_fee = haul_fee_rate_sv * total_item_vol
                    else:
                        haul_fee = 0
                    logger.debug("haul fee is: %s", haul_fee)
                    tax_rate = get_tax_rate_from_database(item_id)
                    # buyback_price = calculate_buyback_price(api_data[0]['immediatePrices']['buyPrice5DayMedian'], tax_rate)
                    # buyback_price_itemtotal = quantity * buyback_price
                    # market_price = api_data[0]['immediatePrices']['buyPrice5DayMedian']
                    # market_price_itemtotal = quantity * market_price
                    # 
                    buyback_price = calculate_buyback_price(item_data['immediatePrices']['buyPrice5DayMedian'], tax_rate)
                    buyback_price_itemtotal = quantity * buyback_price
                    market_price = item_data['immediatePrices']['buyPrice5DayMedian']
                    market_price_itemtotal = quantity * market_price



                    processed_items.append({
                        'item_id': item_id,
                        'item_name': item_name,
                        'quantity': quantity,
                        'tax_rate': tax_rate,
                        'buyback_price': buyback_price,
                        'market_price': market_price,
                        'buyback_price_itemtotal': buyback_price_itemtotal,
                        'market_price_itemtotal': market_price_itemtotal,
                        'haul_bool': haul_bool,
                        'item_volume': item_volume,
                        'haul_fee': haul_fee,
                        
                    })  # Include the processed item data
            logger.debug("processed_items: %s", processed_items)
            gtotal_market = sum(item.get('market_price_itemtotal', 0) for item in processed_items)
            gtotal_buyback = sum(item.get('buyback_price_itemtotal', 0) for item in processed_items)

            totals_info = [gtotal_buyback, gtotal_market]           
            nl_db = "\n"
            debug = [api_data]
            # debug = 0
            return render(request, 'buyback/index.html', {'form': form,'processed_items': processed_items, 'totals_info':totals_info, 'debug': debug, 'info_right': info_right})
    else:
        form = ItemForm()
        info_right = 1
    return render(request, 'buyback/index.html', {'form': form, 'debug': debug, 'info_right': info_right})

def all_item_tax_view(request):
    all_items = EveItemTax.objects.all()
    return render(request, 'buyback/all_item_tax.html', {'all_items': all_items})