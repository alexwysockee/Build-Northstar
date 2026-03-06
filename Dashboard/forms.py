#Dashboard/forms.py
from django import forms
from .models import Report
#test
class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['text']
        labels = {'text': 'Enter text'}