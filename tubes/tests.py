from rest_framework.test import APITestCase
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from tubes.models import Unit, ContainerKind, Content, Container, Substance, TransferGroup, TransferLog, TransferPlan
from django.conf import settings
from mock import patch


class BaseTransferTestCase(APITestCase):
	def setUp(self):
		""" Set up a bunch of common test data, and log the client in """
		self.ml = Unit.objects.create(long_name='Millilitres', short_name='ml', to_ml=1.0)
		self.ml.save()
		self.ul = Unit.objects.create(long_name='Microlitres', short_name='ul', to_ml=0.001)
		self.ul.save()
		tube = ContainerKind.objects.create(name='Tube', quantity=1.0, unit=self.ml)
		tube.save()
		self.tubeA = Container.objects.create(name='TubeA', kind=tube)
		self.tubeB = Container.objects.create(name='TubeB', kind=tube)
		self.tubeC = Container.objects.create(name='TubeC', kind=tube)
		self.tubeA.save()
		self.tubeB.save()
		self.tubeB.save()
		self.cytarabine = Substance.objects.create(name='Cytarabine')
		self.cytarabine.save()
		self.bortezomib = Substance.objects.create(name='Bortezomib')
		self.bortezomib.save()
		contentA = Content.objects.create(substance=self.cytarabine, concentration=25, quantity=0.5, unit=self.ml, container=self.tubeA)
		contentA.save()
		user = User.objects.create_user('tmp', 'tmp@gmail.com', 'tmp')
		self.transfer_url = reverse('container-transfer', args=(1,))

@patch.object(APIView, 'authentication_classes', new = [TokenAuthentication])
@patch.object(APIView, 'permission_classes', new = [AllowAny])
class TransferTestCase(BaseTransferTestCase):
	def test_simple_transfer(self):		
		""" Test that we can transfer a single chemical from tube A to an empty tube B """
		response = self.client.post(self.transfer_url, {'into': 2})
		self.assertEqual(response.data['destination']['content_volume'], 0.5)

	def test_transfer_into_same_substance(self):
		""" Check that the transfer works if B already has some of what's in A """
		Content.objects.create(substance=self.cytarabine, concentration=50, quantity=0.25, unit=self.ml, container=self.tubeB).save()
		response = self.client.post(self.transfer_url, {'into': 2})
		self.assertEqual(response.data['destination']['content_volume'], 0.75)
		self.assertAlmostEqual(response.data['destination']['contents'][0]['concentration'], 100/3.0)

	def test_mix_units(self):
		""" Check that you can transfer even if the quantities and units in the database are mixed """
		Content.objects.create(substance=self.cytarabine, concentration=50, quantity=250, unit=self.ul, container=self.tubeB).save()
		response = self.client.post(self.transfer_url, {'into': 2})
		self.assertEqual(response.data['destination']['content_volume'], 0.75)
		self.assertAlmostEqual(response.data['destination']['contents'][0]['concentration'], 100/3.0)

	def test_transfer_multiple_chemicals_with_logs(self):
		""" Check that multiple chemicals can be transferred successfully, and that such a transfer produces the log entries we expect. """
		Content.objects.create(substance=self.cytarabine, concentration=25, quantity=0.20, unit=self.ml, container=self.tubeB).save()
		Content.objects.create(substance=self.bortezomib, concentration=25, quantity=0.20, unit=self.ml, container=self.tubeA).save()
		response = self.client.post(self.transfer_url, {'into': 2})
		expected_logs = [
			'Transfer of 0.5 ml of Cytarabine from TubeA to TubeB',
 			'Transfer of 0.2 ml of Bortezomib from TubeA to TubeB'
 		]

		self.assertEqual([str(x) for x in TransferLog.objects.all()], expected_logs)

	def test_chain_transfer(self):
		""" Check that a series of transfers between multiple tubes with stuff in two of them produces the expected result """

		# There's no API endpoint for making TransferGroups and TransferPlans so we test the DB directly.
		# Adding them would be fairly trivial though, just a matter of adding serializers and mdoels.
		Content.objects.create(substance=self.cytarabine, concentration=25, quantity=0.20, unit=self.ml, container=self.tubeB).save()
		transfers = TransferGroup()
		transfers.save()
		TransferPlan(transfer_group = transfers, containerA=self.tubeA, containerB=self.tubeB, order=0).save()
		TransferPlan(transfer_group = transfers, containerA=self.tubeB, containerB=self.tubeC, order=1).save()
		TransferPlan(transfer_group = transfers, containerA=self.tubeC, containerB=self.tubeA, order=2).save()
		transfers.execute()
		self.tubeA.refresh_from_db()
		self.assertEqual(self.tubeA.contents.all()[0].quantity, 0.7)

	def test_transfer_overflow(self):
		""" Check for an error response if tube B would overflow """
		Content.objects.create(substance=self.cytarabine, concentration=25, quantity=0.75, unit=self.ml, container=self.tubeB).save()
		response = self.client.post(self.transfer_url, {'into': 2})
		self.assertEqual(response.status_code, 400)

	def test_transfer_404_exception(self):
		""" Check that we get a 404 when attempting to transfer into a non-existant container """
		response = self.client.post(self.transfer_url, {'into': 5})
		self.assertEqual(response.status_code, 404)

@patch.object(APIView, 'permission_classes', new = [IsAuthenticated])
@patch.object(APIView, 'authentication_classes', new = [SessionAuthentication])
class TestAuth(BaseTransferTestCase):
	def test_transfer_requires_auth(self):
		response = self.client.post(self.transfer_url, {'into': 2})
		self.assertEqual(response.status_code, 403)

	def test_bad_credentials(self):
		self.client.login(username='nope', password='wrong')
		response = self.client.post(self.transfer_url, {'into': 2})
		self.assertEqual(response.status_code, 403)

	def test_transfer_with_login(self):
		self.client.login(username='tmp', password='tmp')
		response = self.client.post(self.transfer_url, {'into': 2})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(TransferGroup.objects.first().executed_by.username, 'tmp')
