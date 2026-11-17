from django import forms

class FlatCostForm(forms.Form):
    flat_cost = forms.DecimalField(label='Spoopy Newbies flat price (ISK)', min_value=0, max_digits=20, decimal_places=2)

class JitaBuyPercentageForm(forms.Form):
    jita_buy_percentage = forms.DecimalField(label='Alliance Jita buy rate (%)', min_value=0, max_value=100)


class ItemForm(forms.Form):
    item_name = forms.CharField(label='Items', widget=forms.Textarea(attrs={
        'placeholder': 'Tritanium\t10,000\nPyerite\t5,000', 'spellcheck': 'false'}))



class ReviewStatusForm(forms.Form):
    needs_review = forms.TypedChoiceField(
        label='Review status', choices=[('', 'Choose review status'), ('true', 'Needs review'), ('false', 'Reviewed')],
        coerce=lambda value: value == 'true')


class OutsiderRateForm(forms.Form):
    outsider_jita_buy_percentage = forms.DecimalField(label='Out-of-alliance Jita rate (%)',
        min_value=0, max_value=100,
        help_text='Stored on each item in this selection.')


class CorpRateForm(forms.Form):
    corp_jita_buy_percentage = forms.DecimalField(label='Spoopy Newbies Jita rate (%)',
        min_value=0, max_value=100,
        help_text='Stored on each item in this selection.')


class ItemTaxForm(JitaBuyPercentageForm, FlatCostForm, OutsiderRateForm, CorpRateForm):
    hauling_fee = forms.BooleanField(label='Hauling fee', required=False)
    needs_review = forms.BooleanField(label='Needs review', required=False)


class LegacyItemForm(ItemForm):
    item_name = forms.CharField(label='Item Name', widget=forms.Textarea(attrs={
        'class': 'form-control focus:ring-2 h-24 ring-inset ring-srcblue col-span-3 px-2 text-srcwhite bg-srcgray-dark outline-none',
        'spellcheck': 'false'}))
