import datetime

from django.db import models
from django.utils import timezone
# Create your models here.
# from config.utils import get_group_name_from_api
    
class EveItemTax(models.Model):
    taxid = models.AutoField(primary_key=True)
    type_id = models.IntegerField(default=0)
    group_id = models.IntegerField(default=0)  # Example default value
    type_name = models.CharField(max_length=255, default='')
    # amarr_buy_percentage = models.FloatField(default=0.0)  # Example default value
    jita_buy_percentage = models.FloatField(default=0.0)  # Example default value
    flat_cost = models.DecimalField(max_digits=20, decimal_places=2)  # posgres cant int
    hauling_fee = models.BooleanField(default=False)  # Example default value
    # jita_sell_percentage = models.FloatField(default=0.0)  # Example default value
    # effective_rate = models.FloatField(default=0.0)  # Example default value
    group = models.CharField(max_length=255, default='', blank=True)
    category_id = models.IntegerField(null=True, blank=True)
    category_name = models.CharField(max_length=255, null=True, blank=True)

    needs_review = models.BooleanField(default=False)
    needs_update = models.BooleanField(default=True)


    # def save(self, *args, **kwargs):
    #     if not self.group:
    #         self.group = str(self.group_id)
    #     super().save(*args, **kwargs)

    def __str__(self):
        return self.type_name
