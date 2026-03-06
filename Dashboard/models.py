from django.db import models
#test
# Create your models here.

class Report(models.Model):
    # A Report the user is looking at
    text = models.CharField(max_length=200)
    date_added = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        # Return a string representation of the model
        return self.text


class Entry(models.Model):
    # Information and link to a Report
    Report = models.ForeignKey(Report, on_delete=models.CASCADE)
    text = models.TextField()
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Entries'

    def __str__(self):
        # Return a string representation of the model
        return f"{self.text[:50]}..." 