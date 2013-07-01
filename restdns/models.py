from django.db import models
from django.db.models.signals import pre_save, post_save, post_delete
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.dispatch import receiver

from .fields import JSONField
from .record_types import validate_parameters, validate_name, RECORD_TYPES


class ExportMixIn(object):

    EXPORTABLES = ['id']

    def export(self):
        return dict([(x, getattr(self, x)) for x in self.EXPORTABLES])


class UpdateMixIn(object):

    UPDATABLE = []

    def update(self, update_dict):
        for name in self.UPDATABLE:
            if name in update_dict:
                if isinstance(self.__dict__[name], dict) and isinstance(update_dict[name], dict):
                    # Handle update of second level dicts
                    self.__dict__[name].update(update_dict[name])
                else:
                    self.__dict__[name] = update_dict[name]


class Zone(models.Model, ExportMixIn, UpdateMixIn):

    """ A DNS zone.
    """

    EXPORTABLES = ('name', 'refresh', 'retry', 'expire', 'minimum', 'serial',
                   'rname', 'primary_ns', 'url', 'records_url')
    UPDATABLE = ('refresh', 'retry', 'expire', 'minimum', 'rname', 'primary_ns')

    name = models.CharField(max_length=255, unique=True, validators=[validate_name, lambda x:x.rstrip('.')])
    refresh = models.IntegerField(default=86400, validators=[MinValueValidator(0), MaxValueValidator(2 ** 32 - 1)])
    retry = models.IntegerField(default=7200, validators=[MinValueValidator(0), MaxValueValidator(2 ** 32 - 1)])
    expire = models.IntegerField(default=3600000, validators=[MinValueValidator(0), MaxValueValidator(2 ** 32 - 1)])
    minimum = models.IntegerField(default=172800, validators=[MinValueValidator(0), MaxValueValidator(2 ** 32 - 1)])
    serial = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(2 ** 32 - 1)])
    rname = models.CharField(max_length=255, validators=[validate_name])
    primary_ns = models.CharField(max_length=255, validators=[validate_name])

    created_on = models.DateTimeField(auto_now=True, auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True, auto_now_add=True)

    def clean(self):
        self.name = self.name.rstrip('.')  # Strip the trailing dot of zone names

    @property
    def url(self):
        return self.get_absolute_url()

    @property
    @models.permalink
    def records_url(self):
        return 'records', [self.name]

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return 'zone', [self.name]


@receiver(pre_save, sender=Zone)
def increment_serial(sender, instance, **kwargs):
    instance.serial += 1


class Record(models.Model, ExportMixIn, UpdateMixIn):

    """ A record for a DNS zone.
    """

    EXPORTABLES = ('id', 'name', 'type', 'parameters', 'url')
    UPDATABLE = ('name', 'type', 'parameters')

    TYPE_CHOICES = [(t, t.upper()) for t in RECORD_TYPES]

    zone = models.ForeignKey(Zone)
    name = models.CharField(max_length=255, validators=[validate_name], blank=True)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    parameters = JSONField(default={})

    @property
    def url(self):
        return self.get_absolute_url()

    def __unicode__(self):
        u'%s (%s) for %s' % (self.name, self.type.upper(), self.zone)

    def clean(self):
        self.parameters = validate_parameters(self.type, self.parameters)

    @models.permalink
    def get_absolute_url(self):
        return 'record', [self.zone.name, self.id]


@receiver([post_save, post_delete], sender=Record)
def increment_zone_serial(sender, instance, **kwargs):
    instance.zone.save()  # Force serial of zone to be incremented


@receiver(pre_save, sender=Record)
def validate_record(sender, instance, **kwargs):
    pass