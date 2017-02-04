from rest_framework import serializers

from tubes.models import Container, Content, ContainerKind


class HasUnit(serializers.ModelSerializer):
	""" HasUnit just provides a unit field for serializers """
	unit = serializers.SlugRelatedField(slug_field='short_name', read_only=True)

class ContentSerializer(HasUnit):
	""" Serialize a content item, e.g. "0.5 ml of Acid"   """
	substance = serializers.SlugRelatedField(slug_field='name', read_only=True)

	class Meta:
		model = Content
		fields = ('substance', 'quantity', 'unit', 'concentration')


class ContainerKindSerializer(HasUnit):
	""" Serialize a container kind, e.g. "a 1ml test tube" """
	class Meta:
		model = ContainerKind
		fields = ('name', 'quantity', 'unit')

class ContainerSerializer(serializers.ModelSerializer):
	""" Serialize a full container, including its contents and its container kind """
	kind = ContainerKindSerializer(read_only=True)
	contents = ContentSerializer(many=True, read_only=True)
	class Meta:
		model = Container
		fields = ('name', 'kind', 'contents', 'content_volume')