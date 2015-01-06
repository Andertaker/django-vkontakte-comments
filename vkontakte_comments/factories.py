import random

from django.utils import timezone
import factory
from vkontakte_api.factories import DjangoModelNoCommitFactory
from vkontakte_users.factories import UserFactory

from . models import Comment


class CommentFactory(DjangoModelNoCommitFactory):
    date = factory.LazyAttribute(lambda o: timezone.now())

    owner = factory.SubFactory(UserFactory)
    object = factory.SubFactory(UserFactory)
    author = factory.SubFactory(UserFactory)
    remote_id = factory.LazyAttributeSequence(lambda o, n: '%s_%s' % (o.owner.remote_id, n))

    class Meta:
        model = Comment
