from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='conversations',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('from_user', models.BooleanField()),
                ('message_number', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='home.conversation')),
            ],
            options={
                'ordering': ['message_number'],
            },
        ),
        migrations.CreateModel(
            name='AudioRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wav_path', models.CharField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audio_records',
                    to='home.conversation')),
                ('text_message', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audio_records',
                    to='home.message')),
            ],
        ),
    ]
