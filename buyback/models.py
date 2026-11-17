import datetime
import uuid

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
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
    corp_jita_buy_percentage = models.FloatField(db_default=0.85,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text='Spoopy Newbies fraction stored on this item (0.85 = 85%).')
    outsider_jita_buy_percentage = models.FloatField(db_default=0.85,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text='Out-of-alliance fraction stored on this item (0.85 = 85%).')
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


class MarketGroup(models.Model):
    """CCP's market browser hierarchy, independent of inventory groups."""
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='children')

    class Meta:
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class MarketType(models.Model):
    """Reference mapping only; business rates stay on EveItemTax."""
    type_id = models.PositiveIntegerField(primary_key=True)
    market_group = models.ForeignKey(MarketGroup, on_delete=models.CASCADE,
                                     related_name='market_types')


class ContractConnection(models.Model):
    """Shared staff authorization. Credential fields contain only Fernet ciphertext."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    authorization_id = models.UUIDField(default=uuid.uuid4, editable=False)
    connected_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=255)
    corporation_id = models.BigIntegerField()
    owner_hash = models.CharField(max_length=255, blank=True)
    access_ciphertext = models.TextField()
    refresh_ciphertext = models.TextField()
    expires_at = models.DateTimeField()
    connected_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='contract_connection_singleton')]


class BuybackContract(models.Model):
    contract_id = models.BigIntegerField(primary_key=True)
    corporation_id = models.BigIntegerField(db_index=True)
    data = models.JSONField()
    synced_at = models.DateTimeField()

    class Meta:
        ordering = ['-contract_id']


class EveStaffIdentity(models.Model):
    character_id = models.BigIntegerField(primary_key=True)
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='eve_staff_identity')
    character_name = models.CharField(max_length=255)
