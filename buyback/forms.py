from django import forms


class ItemForm(forms.Form):
    item_name = forms.CharField(label='Item Name', widget=forms.Textarea(attrs={'class': 'form-control focus:ring-2 h-24 ring-inset ring-srcblue col-span-3 px-2 text-srcwhite bg-srcgray-dark outline-none'}))

