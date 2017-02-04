from django.contrib import admin
from models import Unit, Container, ContainerKind, Content, Substance, TransferLog

admin.site.register([Unit, Container, ContainerKind, Content, Substance, TransferLog])
