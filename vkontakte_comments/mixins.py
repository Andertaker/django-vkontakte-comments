# -*- coding: utf-8 -*-
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction

from .models import Comment


log = logging.getLogger('vkontakte_comments')


class CommentableModelMixin(models.Model):

    comments_count = models.PositiveIntegerField('Comments', null=True, help_text='The number of comments of this item')

    class Meta:
        abstract = True

    @property
    def comments(self):
        # TODO: set this attr by related_name
        return Comment.objects.filter(object_id=self.pk,
                                      object_content_type=ContentType.objects.get_for_model(self))

    @transaction.commit_on_success
    def fetch_comments(self, *args, **kwargs):
        return Comment.remote.fetch_by_object(object=self, *args, **kwargs)

    @property
    def comments_remote_related_name(self):
        raise NotImplementedError()
