# -*- coding: utf-8 -*-
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
import logging
import re

from vkontakte_api.decorators import fetch_all
from vkontakte_api.mixins import CountOffsetManagerMixin, AfterBeforeManagerMixin, OwnerableModelMixin, AuthorableModelMixin
from vkontakte_api.models import VkontakteModel, VkontakteCRUDModel
log = logging.getLogger('vkontakte_comments')


def get_methods_namespace(object):
    return object.methods_namespace or object.__class__.remote.methods_namespace


class CommentRemoteManager(CountOffsetManagerMixin, AfterBeforeManagerMixin):

    @transaction.commit_on_success
    @fetch_all(default_count=100)
    def fetch_album(self, album, sort='asc', need_likes=True, **kwargs):
        raise NotImplementedError

    @transaction.commit_on_success
    @fetch_all(default_count=100)
    def fetch_by_object(self, object, sort='asc', need_likes=True, **kwargs):
        if sort not in ['asc', 'desc']:
            raise ValueError("Attribute 'sort' should be equal to 'asc' or 'desc'")

        if 'after' in kwargs:
            if kwargs['after'] and sort == 'asc':
                raise ValueError("Attribute `sort` should be equal to 'desc' with defined `after` attribute")

        kwargs["methods_namespace"] = get_methods_namespace(object)

        # owner_id идентификатор пользователя или сообщества, которому принадлежит фотография.
        # Обратите внимание, идентификатор сообщества в параметре owner_id необходимо указывать со знаком "-" — например, owner_id=-1 соответствует идентификатору сообщества ВКонтакте API (club1)
        # int (числовое значение), по умолчанию идентификатор текущего пользователя

        kwargs['owner_id'] = object.owner_remote_id

        # идентификатор объекта к которому оставлен комментарий.
        # напр 'video_id', 'photo_id'
        # int (числовое значение), обязательный параметр
        kwargs[object.comments_remote_related_name] = object.remote_id

        # need_likes 1 — будет возвращено дополнительное поле likes. По умолчанию поле likes не возвращается.
        # флаг, может принимать значения 1 или 0
        kwargs['need_likes'] = int(need_likes)

        # sort порядок сортировки комментариев (asc — от старых к новым, desc - от новых к старым)
        # строка
        kwargs['sort'] = sort

        object_ct = ContentType.objects.get_for_model(object)
        kwargs['extra_fields'] = {
            'object_content_type': object_ct,
            'object_content_type_id': object_ct.pk,
            'object_id': object.pk,
            'object': object,
        }

        return super(CommentRemoteManager, self).fetch(**kwargs)


class Comment(AuthorableModelMixin, VkontakteModel, VkontakteCRUDModel):

    fields_required_for_update = ['comment_id', 'owner_id', 'methods_namespace']
    _commit_remote = False

    remote_id = models.CharField(
        u'ID', primary_key=True, max_length=20, help_text=u'Уникальный идентификатор', unique=True)

    object_content_type = models.ForeignKey(ContentType, related_name='content_type_objects_vkontakte_comments')
    object_id = models.PositiveIntegerField(db_index=True)
    object = generic.GenericForeignKey('object_content_type', 'object_id')

    date = models.DateTimeField(help_text=u'Дата создания', db_index=True)
    text = models.TextField(u'Текст сообщения')
    # attachments - присутствует только если у сообщения есть прикрепления,
    # содержит массив объектов (фотографии, ссылки и т.п.). Более подробная
    # информация представлена на странице Описание поля attachments

    # TODO: implement with tests
#    likes = models.PositiveIntegerField(u'Кол-во лайков', default=0)

    objects = models.Manager()
    remote = CommentRemoteManager(remote_pk=('remote_id',), version=5.27, methods={
        'get': 'getComments',
        'create': 'createComment',
        'update': 'editComment',
        'delete': 'deleteComment',
        'restore': 'restoreComment',
    })

    class Meta:
        verbose_name = u'Комментарий Вконтакте'
        verbose_name_plural = u'Комментарии Вконтакте'

    @property
    def owner_remote_id(self):
        # return self.photo.remote_id.split('_')[0]

        if self.object.owner_content_type.model == 'user':
            return self.object.owner_id
        else:
            return -1 * self.object.owner_id

        '''
        if self.author_content_type.model == 'user':
            return self.author_id
        else:
            return -1 * self.author_id
        '''

    @property
    def remote_id_short(self):
        return self.remote_id.split('_')[1]

    def prepare_create_params(self, from_group=False, **kwargs):
        if self.author == self.object.owner and self.author_content_type.model == 'group':
            from_group = True
        kwargs.update({
            'owner_id': self.owner_remote_id,
            'message': self.text,
#            'reply_to_comment': self.reply_for.id if self.reply_for else '',
            'from_group': int(from_group),
            'attachments': kwargs.get('attachments', ''),
            'methods_namespace': get_methods_namespace(self.object),
            self.object.comments_remote_related_name: self.object.remote_id,
        })
        return kwargs

    def prepare_update_params(self, **kwargs):
        kwargs.update({
            'owner_id': self.owner_remote_id,
            'comment_id': self.remote_id_short,
            'message': self.text,
            'attachments': kwargs.get('attachments', ''),
            'methods_namespace': get_methods_namespace(self.object),
        })
        return kwargs

    def prepare_delete_params(self):
        return {
            'owner_id': self.owner_remote_id,
            'comment_id': self.remote_id_short,
            'methods_namespace': get_methods_namespace(self.object),
        }

    def parse_remote_id_from_response(self, response):
        if response:
            return '%s_%s' % (self.owner_remote_id, response)
        return None

    def get_or_create_group_or_user(self, remote_id):
        # TODO: refactor this method, may be put it to AuthorableMixin
        from vkontakte_groups.models import Group
        from vkontakte_users.models import User

        if remote_id > 0:
            Model = User
        elif remote_id < 0:
            Model = Group
        else:
            raise ValueError("remote_id shouldn't be equal to 0")

        return Model.objects.get_or_create(remote_id=abs(remote_id))

    def parse(self, response):
        # undocummented feature of API. if from_id == 101 -> comment by group
        if response['from_id'] == 101:
            self.author = self.object.owner
        else:
            self.author = self.get_or_create_group_or_user(response.pop('from_id'))[0]

        # TODO: add parsing attachments and polls
        if 'attachments' in response:
            response.pop('attachments')
        if 'poll' in response:
            response.pop('poll')

        if 'message' in response:
            response['text'] = response.pop('message')

        super(Comment, self).parse(response)
        if 'object' in self.__dict__:
            self.object = self.__dict__['object']  # TODO: check is it should be already saved or not

        if '_' not in str(self.remote_id):
            self.remote_id = '%s_%s' % (self.owner_remote_id, self.remote_id)
