#Dashboard/forms.py
from django import forms
from .models import Report, Entry, SalesProduct, DailySale
#test
class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['text']
        labels = {'text': 'Report title'}
        widgets = {'text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Report title'})}


class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ['text']
        labels = {'text': 'Entry'}
        widgets = {'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter entry text...'})}


class SalesProductForm(forms.ModelForm):
    class Meta:
        model = SalesProduct
        fields = ['name', 'price', 'goal']
        labels = {'name': 'Product name', 'price': 'Price', 'goal': 'Monthly goal'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'goal': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


class DailySaleForm(forms.ModelForm):
    class Meta:
        model = DailySale
        fields = ['product', 'date', 'amount']
        labels = {'product': 'Product', 'date': 'Date', 'amount': 'Amount'}
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        if not self.instance.pk and 'date' not in (self.data or {}):
            self.initial.setdefault('date', timezone.now().date())