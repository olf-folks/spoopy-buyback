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
from .models import EveItemTax  # Import your model

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

def index(request):
    debug = []
    info_right = 2
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            items_input = form.cleaned_data['item_name']  # Get the input text from the form
            items_list = items_input.split('\n')  # Split input by lines
            
            # Create a list to store processed item data
            processed_items = []
            
            for item_input in items_list:
                item_parts = item_input.strip().split(' ')  # Split item input into parts (item_name, quantity)
                if len(item_parts) == 2:
                    item_name, quantity = item_parts
                    janiceurl = 'https://janice.e-351.com/api/rest/v2/pricer?market=2'
                    janiceheaders = {"accept": "application/json", "X-ApiKey": "G9KwKq3465588VPd6747t95Zh94q3W2E", "Content-Type": "text/plain"}
                    janiceresponse = requests.post(janiceurl, item_name, headers=janiceheaders)
                    api_data = janiceresponse.json()

                    
                    
                    item_id = api_data[0]['itemType']['eid']  # Assuming you get the item ID from the API response
                    tax_rate = get_tax_rate_from_database(item_id)
                    buyback_price = calculate_buyback_price(api_data[0]['immediatePrices']['buyPrice5DayMedian'], tax_rate)
                    buyback_price_itemtotal = int(quantity)*buyback_price
                    market_price = api_data[0]['immediatePrices']['buyPrice5DayMedian']
                    market_price_itemtotal = int(quantity)*market_price
                    
                    processed_items.append({
                        'item_name': item_name,
                        'quantity': int(quantity),
                        'tax_rate': tax_rate,
                        'buyback_price': buyback_price,
                        'buyback_price_itemtotal': buyback_price_itemtotal,
                        'market_price_itemtotal': market_price_itemtotal,
                        'api_data': api_data[0],
                    })  # Include the processed item data

                    gtotal_market = sum(item.get('market_price_itemtotal', 0) for item in processed_items)
                    gtotal_buyback = sum(item.get('buyback_price_itemtotal', 0) for item in processed_items)

                    totals_info = [gtotal_buyback, gtotal_market]

            debug = [processed_items, totals_info]
            debug = 0
            return render(request, 'buyback/index.html', {'form': form,'processed_items': processed_items,'totals_info':totals_info, 'debug': debug, 'info_right': info_right})
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