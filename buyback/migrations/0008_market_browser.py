from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('buyback', '0007_eveitemtax_needs_update')]
    operations = [
        migrations.CreateModel(name='MarketGroup', fields=[
            ('id', models.PositiveIntegerField(primary_key=True, serialize=False)),
            ('name', models.CharField(max_length=255)),
            ('parent', models.ForeignKey(blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='children', to='buyback.marketgroup')),
        ], options={'ordering': ['name', 'id']}),
        migrations.CreateModel(name='MarketType', fields=[
            ('type_id', models.PositiveIntegerField(primary_key=True, serialize=False)),
            ('market_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                related_name='market_types', to='buyback.marketgroup')),
        ]),
    ]
