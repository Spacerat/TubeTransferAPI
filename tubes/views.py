from django.shortcuts import render

from tubes.serializers import ContainerSerializer
from tubes.models import Container, TransferGroup, TransferPlan, TransferError, Content
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import detail_route

from django.shortcuts import get_object_or_404


class ContainerViewSet(viewsets.ModelViewSet):
	""" This model implements the /containers/ endpoints. Since it's based on 
	ModelViewSet it gets GET/PUSH/etc for free.  """
	queryset = Container.get_full_queryset()
	serializer_class = ContainerSerializer

	@detail_route(methods=['post'])	
	def transfer(self, request, *args, **kwargs):
		""" This is the endpoint for /containers/<id>/transfer """
		user = request.user
		transfer_from = self.get_object()
		transfer_to = get_object_or_404(Container, pk=request.data['into'])
		
		transfer_from.transfer_to(transfer_to, user=user)
	
		return Response({
			'origin': self.get_serializer(transfer_from).data,
			'destination': self.get_serializer(transfer_to).data
		})

# We could easily add ModelViewSets for every model, enabling GET/PUSH/PUT/UPDATE/DELTE support 
# for every model we want it for. However, doing that would be way outside the scope of this task.