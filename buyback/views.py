

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

def index(request):
    debug = []
    info_right = 2
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            item_name = form.cleaned_data['item_name']
            # Make API request
            #api_url = f'https://api.example.com/items?name={item_name}'
            #response = requests.get(api_url)
            #api_data = response.json()
            janiceurl = 'https://janice.e-351.com/api/rest/v2/pricer?market=2'
            janiceheaders={"accept": "application/json", "X-ApiKey": "G9KwKq3465588VPd6747t95Zh94q3W2E", "Content-Type": "text/plain"}
            janiceresponse = requests.post(janiceurl, item_name, headers=janiceheaders)
            api_data = janiceresponse.json()
            debug = [janiceurl, janiceheaders, api_data]
            return render(request, 'buyback/index.html', {'api_data': api_data, 'debug': debug, 'info_right': info_right})
    else:
        form = ItemForm()
        info_right = 1
    return render(request, 'buyback/index.html', {'form': form, 'debug': debug, 'info_right': info_right})   


# haul no Use   isk to m3   200 isk per m3


# none should have both flat and market rate


# jita buy * percent of jita buy