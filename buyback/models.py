import datetime

from django.db import models
from django.utils import timezone
# Create your models here.

    
class EveItemTax(models.Model):
    taxid = models.AutoField(primary_key=True)
    type_id = models.IntegerField(default=0)
    group_id = models.IntegerField(default=0)  # Example default value
    type_name = models.CharField(max_length=255, default='')
    # amarr_buy_percentage = models.FloatField(default=0.0)  # Example default value
    jita_buy_percentage = models.FloatField(default=0.0)  # Example default value
    flat_cost = models.IntegerField(default=0)  # Example default value
    hauling_fee = models.BooleanField(default=False)  # Example default value
    # jita_sell_percentage = models.FloatField(default=0.0)  # Example default value
    # effective_rate = models.FloatField(default=0.0)  # Example default value

    def __str__(self):
        return self.type_name