from django.db import migrations


def create_sample_data(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Motorcycle = apps.get_model('market', 'Motorcycle')

    seller, _ = User.objects.get_or_create(username='sample_seller')

    Motorcycle.objects.create(
        title='Yamaha NMAX 2020',
        description='Well-maintained NMAX with original parts, low km.',
        start_price='15000000.00',
        seller=seller,
    )
    Motorcycle.objects.create(
        title='Honda PCX 2018',
        description='Single owner, good condition, service history available.',
        start_price='12000000.00',
        seller=seller,
    )
    Motorcycle.objects.create(
        title='Kawasaki Ninja 250',
        description='Clean, upgraded suspension, great for weekend rides.',
        start_price='35000000.00',
        seller=seller,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_sample_data),
    ]
