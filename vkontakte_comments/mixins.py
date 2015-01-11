# -*- coding: utf-8 -*-
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
import logging

from .models import Comment
log = logging.getLogger('vkontakte_comments')


class CommentableModelMixin(models.Model):

    comments = generic.GenericRelation(Comment, related_name='%(class)ss', verbose_name='Comments',
                                       content_type_field='object_content_type', object_id_field='object_id')
    comments_count = models.PositiveIntegerField('Comments', null=True,
                                                 help_text='The number of comments of this item')

    class Meta:
        abstract = True

    def parse(self, response):
        if 'comments' in response:
            value = response.pop('comments')
            if isinstance(value, int):
                response['comments_count'] = value
            elif isinstance(value, dict) and 'count' in value:
                response['comments_count'] = value['count']
        super(CommentableModelMixin, self).parse(response)

    @transaction.commit_on_success
    def fetch_comments(self, *args, **kwargs):
        return Comment.remote.fetch_by_object(object=self, *args, **kwargs)

    @property
    def comments_remote_related_name(self):
        raise NotImplementedError()

    def parse(self, response):
        if 'comments' in response:
            value = response.pop('comments')
            if isinstance(value, int):
                response['comments_count'] = value
            elif isinstance(value, dict) and 'count' in value:
                response['comments_count'] = value['count']
        super(CommentableModelMixin, self).parse(response)
