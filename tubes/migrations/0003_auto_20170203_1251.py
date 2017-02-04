# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-03 12:51
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tubes', '0002_auto_20170203_1156'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='containercontentlog',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='containercontentlog',
            name='container',
        ),
        migrations.RemoveField(
            model_name='containercontentlog',
            name='substance',
        ),
        migrations.RemoveField(
            model_name='containercontentlog',
            name='transfer_group',
        ),
        migrations.RemoveField(
            model_name='containercontentlog',
            name='unit',
        ),
        migrations.AlterUniqueTogether(
            name='transferlog',
            unique_together=set([('containerA', 'containerB', 'transfer_group', 'substance'), ('transfer_group', 'order')]),
        ),
        migrations.DeleteModel(
            name='ContainerContentLog',
        ),
    ]
