from django.db import migrations, models
from django.core.validators import MinValueValidator, MaxValueValidator


class Migration(migrations.Migration):
    dependencies = [('buyback', '0009_outsider_rate')]
    operations = [migrations.AddField(model_name='eveitemtax', name='corp_jita_buy_percentage',
        field=models.FloatField(null=True, blank=True,
            validators=[MinValueValidator(0), MaxValueValidator(1)],
            help_text='Spoopy Newbies fraction; blank uses the configured corporation default.'))]
