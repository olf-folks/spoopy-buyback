from django import forms

class FlatCostForm(forms.Form):
    flat_cost = forms.DecimalField(label='Flat Cost', min_value=0)

class JitaBuyPercentageForm(forms.Form):
    jita_buy_percentage = forms.DecimalField(label='Jita Buy Percentage', min_value=0, max_value=100)


class ItemForm(forms.Form):
    item_name = forms.CharField(label='Item Name', widget=forms.Textarea(attrs={'class': 'form-control focus:ring-2 h-24 ring-inset ring-srcblue col-span-3 px-2 text-srcwhite bg-srcgray-dark outline-none'}))

