from __future__ import unicode_literals

from rest_framework.exceptions import APIException
from django.db.models import F, Sum
from django.db import models, transaction
from django.db.models import Prefetch
from django.contrib.auth.models import AnonymousUser

class TransferError(APIException):
    """ Base class for a logical error during a transfer """
    status_code = 400

class Unit(models.Model):
    """ A unit keeps track of the volume of a given unit relative to 1ml """
    short_name = models.CharField(max_length=5)
    long_name = models.CharField(max_length=30, unique=True)
    to_ml = models.FloatField()

    def __str__(self):
        return self.long_name

class VolumeModel(models.Model):
    """ A base class for any table which needs to store a volume.
        Contains a qunatity and a unit.  """
    quantity = models.FloatField()
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='+')

    def to_ml(self):
        """ Return the volume of this item in milliliters """
        return self.quantity * self.unit.to_ml

    def set_ml(self, ml):
        """ Set quantity such that quantity * unit = ml """
        self.quantity = ml / self.unit.to_ml 
    volume = property(to_ml)

    def __str__(self):
        return "{} {}".format(self.quantity, self.unit.short_name)

    class Meta:
        abstract = True

class ContainerKind(VolumeModel):
    """ A ContainerKind is a volume with a name (e.g. "ScienceCorp's 1ml Test Tube")"""
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Container(models.Model):
    """ A Container represents an instance of a real container """
    name = models.CharField(max_length=100, unique=True)
    kind = models.ForeignKey(ContainerKind, on_delete=models.PROTECT)

    @property
    def container_volume(self):
        """ Get the max volume of this container in ml """
        return self.kind.volume

    @property
    def content_volume(self):
        """ Get the current volume of things in this container """

        # aggregate, Sum() and F-expressions are used to do the computation entirely on the database.
        aggregate = self.contents.aggregate(content_volume=Sum(F('quantity') * F('unit__to_ml')))['content_volume']
        return aggregate if aggregate else 0

    def transfer_to(self, into, user=None):
        """ Attempt to immediately transfer the entirety this container's contents into another container """
        with transaction.atomic():
            transfers = TransferGroup()
            transfers.save()
            transfer = TransferPlan(
                transfer_group = transfers,
                containerA=self, 
                containerB=into,
                )
            transfer.save()
            transfers.execute(user=user)

    @classmethod
    def get_full_queryset(cls):
        """ This returns a queryset for containers which uses JOINS to select all data for each container, instead of having
        to SELECT for every single container's content and unit, which could get very slow if you have containers containing many 
        chemicals. """
        return cls.objects.select_related().prefetch_related(Prefetch('contents', queryset=Content.objects.select_related()))

    def __str__(self):
        return "{} [{}]".format(self.name, self.kind.name)

class Substance(models.Model):
    """ A Substance represents a kind of thing we might put in a container """
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class BaseContent(VolumeModel):
    """ BaseContent is used as a base for actual container contents, and also for content logs """
    substance = models.ForeignKey(Substance)
    container = models.ForeignKey(Container, related_name='contents')
    concentration = models.FloatField() # Micromolars

    def add_content(self, new_content):
        if self.substance != new_content.substance:
            raise TransferError("Cannot combine volumes of different substances")
        my_old = self.volume
        their_old = new_content.volume
        new_vol = my_old + their_old
        self.concentration = (self.concentration * my_old + new_content.concentration * their_old) / new_vol
        self.set_ml(new_vol)


    def __str__(self):
        return "{} {} of {}".format(self.quantity, self.unit.short_name, self.substance.name)

    class Meta(VolumeModel.Meta):
        abstract = True
        unique_together = (('substance', 'container'),)

class Content(BaseContent):
    """ A Content links some quantity of a substance to a container """
    pass

class TransferGroup(models.Model):
    """ A TransferGroup represents a group of transfers to be executed at once.
    After the transfers are executed, the transfer logs will be linked to the transfer group."""
    execution_date = models.DateTimeField(null=True)
    executed_by = models.ForeignKey('auth.user', null=True, related_name='executed_transfers')

    def execute(self, user=None):
        """ Execute a list of transfers """
        transfer_number = 0

        # Execute each one in sequence with a database transaction
        # If anything fails, everything will just be reset.
        with transaction.atomic():
            for transfer in self.transfer_plans.all():
                transfer_number += transfer.execute(transfer_number=transfer_number)

            if not isinstance(user, AnonymousUser):
                self.executed_by = user
                self.save()

class TransferPlan(models.Model):
    """ A TransferPlan is a proposed transfer. It says "transfer everything from A to B" """
    containerA = models.ForeignKey(Container, related_name='+')
    containerB = models.ForeignKey(Container, related_name='+')
    order = models.IntegerField(default=0)
    transfer_group = models.ForeignKey(TransferGroup, related_name='transfer_plans', on_delete=models.CASCADE)
    
    def execute(self, transfer_number=0):
        num_transfers = 0
        
        with transaction.atomic():
            # First check that there's enough room in container B for all of container A
            sum_volume = self.containerA.content_volume + self.containerB.content_volume
            if sum_volume > self.containerB.container_volume:
                # Complain if there would be an overflow
                raise TransferError('{} would overflow'.format(self.containerB.name))
            else:
                # Iterate over the individual chemicals in A, and transfer them one by one to B
                a_contents = self.containerA.contents
                for content in a_contents.all():
                    content_substance = content.substance
                    existing_substance = self.containerB.contents.filter(substance=content.substance)
                    
                    if existing_substance:
                        # If B already contains a substance of that kind, we need to update its quantity and concentration
                        existing_substance = existing_substance.first()
                        existing_substance.add_content(content)
                        existing_substance.save()
                        content.delete()
                    else:
                        # Otherwise simply reassign the content from A to B
                        content.container = self.containerB
                        content.save()
                    # Create a log that this happened, making sure we keep track of the order.
                    log = TransferLog.objects.create(
                        containerA=self.containerA, 
                        containerB=self.containerB,
                        order=transfer_number+num_transfers,
                        transfer_group=self.transfer_group,
                        substance=content.substance,
                        quantity=content.quantity,
                        unit=content.unit
                        )
                    log.save()
                    num_transfers+=1
        return num_transfers


    class Meta:
        unique_together = (('containerA', 'containerB', 'transfer_group'), ('transfer_group', 'order'))
        ordering = ('order',)

class TransferLog(VolumeModel):
    """ A TransferLog logs what exactly was transferred. """
    containerA = models.ForeignKey(Container, related_name='+')
    containerB = models.ForeignKey(Container, related_name='+')
    order = models.IntegerField()
    transfer_group = models.ForeignKey(TransferGroup, related_name='transfer_logs', on_delete=models.PROTECT)
    substance = models.ForeignKey(Substance)

    def __str__(self):
        return "Transfer of {} {} of {} from {} to {}".format(self.quantity, self.unit.short_name, self.substance, self.containerA.name, self.containerB.name)
    
    class Meta:
        unique_together = (('containerA', 'containerB', 'transfer_group', 'substance'), ('transfer_group', 'order'))
        ordering = ('order',)
