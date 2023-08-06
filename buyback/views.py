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






# def parse_user_input(form_data):
#     parsed_input = []
#     input_lines = []
#     logger.debug("form_data input in into parse user input fuction: %s", form_data)
#     items_list = re.split(r'\r?\n', form_data)  # Split using \r\n or \n as the delimiter
#     logger.debug("items_list in parse user input fuction: %s", items_list)
    
#     for item_input in items_list:
#         # item_parts = item_input.strip().split(' ')
#         # if len(item_parts) == 2:
#         #     item_name, quantity = item_parts
#         #     input_lines.append((item_name, quantity))

#         #
#         #  mikio search regex
#         #  
#         # initial_string = "Large YF-12a Smartbomb    2   Smart Bomb          100 m3  1,444,036.44 ISK"
#         initial_string = item_input
#         name = re.search(r'^([\S\ ]*)',initial_string).group(0)
#         quantity = re.search(r"\t([[\d,'\.\ '  ']*)|(?! |\t)[0-9]+",initial_string).group(0).strip()

        

#         if not quantity:
#             quantity = 1
#         else:
#             quantity = int(quantity)
#         print(name)
#         print(quantity)

#         item_name = name
#         logger.debug("regex debug search found name: %s", name)
#         logger.debug("regex debug search found quantity: %s", quantity)
        
#     for item_name, quantity in input_lines:
#         line = f"{item_name} {quantity}"
#         match = re_asset_list.match(line)
#         logger.debug("regex debug Line before matching: %s", line)
#         if match:
#             logger.debug("regex debug Line after matching: %s", line)
#             input_name = match.group(1)
#             # not working with commas
#             #quantity = int(match.group(2))
#             # remove commas in quanity
#             quantity_str = match.group(2).replace(',', '')  # Remove commas from the quantity string
#             input_quantity = int(quantity_str)
#             # group = match.group(3)
#             # category = match.group(4)
#             # size = match.group(5)
#             # slot = match.group(6)
#             # volume = float(match.group(7)) if match.group(7) else 0.0
#             # meta_level = match.group(9)
#             # tech_level = match.group(10)
#             # price_estimate = float(match.group(11)) if match.group(11) else 0.0
            
#             parsed_input.append({
#                 'name': input_name,
#                 'quantity': input_quantity,
#             })

#             # Return the list of parsed items
#     return parsed_input


def parse_user_input(form_data):
    parsed_input = []
    logger.debug("form_data input in into parse user input function: %s", form_data)
    items_list = re.split(r'\r?\n', form_data)  # Split using \r\n or \n as the delimiter
    logger.debug("items_list in parse user input function: %s", items_list)
    
    for item_input in items_list:
        initial_string = item_input
        #name = re.search(r'^(\S+)', initial_string).group(1)            
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
    debug = []
    info_right = 2
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            raw_user_input = form.cleaned_data['item_name']  # Get the input text from the form
            parsed_user_input = parse_user_input(raw_user_input)
            logger.debug("parseduserinput: %s", parsed_user_input)
            api_input = generate_api_input(parsed_user_input)
            quantity = getqtys(parsed_user_input)
            logger.debug("apiinput: %s", api_input)
            janiceurl = 'https://janice.e-351.com/api/rest/v2/pricer?market=2'
            janiceheaders = {"accept": "application/json", "X-ApiKey": "G9KwKq3465588VPd6747t95Zh94q3W2E", "Content-Type": "text/plain"}
            janiceresponse = requests.post(janiceurl, api_input, headers=janiceheaders)
            api_data = janiceresponse.json()
            logger.debug("janiceapijsonresp: %s", api_data)

            # make list of dicts that combines api_data + tax_rate + api_input
            processed_items = []
            for item in parsed_user_input:
                
                item_name = item['name']
                quantity = item['quantity']
                #item_id = api_data[0]['itemType']['eid']  # Assuming you get the item ID from the API response
                #item_data = next((item for item in api_data if item['itemType']['name'] == item_name), None)
                #item_data = next((item for item in api_data if item['itemType']['name'] == item['name']), None)
                #item_data = next((item for item in api_data if item['itemType']['name'] == item_data['itemType']['name']), None)
                item_data = next((api_item for api_item in api_data if api_item['itemType']['name'] == item_name), None)
                if item_data:
                    item_id = item_data['itemType']['eid']
                    tax_rate = get_tax_rate_from_database(item_id)
                    buyback_price = calculate_buyback_price(api_data[0]['immediatePrices']['buyPrice5DayMedian'], tax_rate)
                    buyback_price_itemtotal = quantity * buyback_price
                    market_price = api_data[0]['immediatePrices']['buyPrice5DayMedian']
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
                        
                    })  # Include the processed item data
       
            gtotal_market = sum(item.get('market_price_itemtotal', 0) for item in processed_items)
            gtotal_buyback = sum(item.get('buyback_price_itemtotal', 0) for item in processed_items)

            totals_info = [gtotal_buyback, gtotal_market]           

            debug = [processed_items]
            # debug = 0
            return render(request, 'buyback/index.html', {'form': form,'processed_items': processed_items, 'totals_info':totals_info, 'debug': debug, 'info_right': info_right})
    else:
        form = ItemForm()
        info_right = 1
    return render(request, 'buyback/index.html', {'form': form, 'debug': debug, 'info_right': info_right})
'''
note:
haul no Use   isk to m3   200 isk per m3
none should have both flat and market rate
jita buy * percent of jita buy
'''