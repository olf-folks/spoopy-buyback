from django.db import migrations, models
from django.core.validators import MinValueValidator, MaxValueValidator


class Migration(migrations.Migration):
    dependencies = [('buyback', '0008_market_browser')]
    operations = [migrations.AddField(model_name='eveitemtax',
        name='outsider_jita_buy_percentage', field=models.FloatField(blank=True, null=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text='Out-of-alliance fraction (0.85 = 85%); blank uses the configured default.'))]
