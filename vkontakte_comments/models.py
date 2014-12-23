# -*- coding: utf-8 -*-
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
import logging
import re

from vkontakte_api.decorators import fetch_all
from vkontakte_api.mixins import CountOffsetManagerMixin, AfterBeforeManagerMixin, OwnerableModelMixin
from vkontakte_api.models import VkontakteModel, VkontakteCRUDModel
from vkontakte_groups.models import Group
#from vkontakte_video.models import Video

from vkontakte_users.models import User
#import signals
log = logging.getLogger('vkontakte_comments')


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

        # owner_id идентификатор пользователя или сообщества, которому принадлежит фотография.
        # Обратите внимание, идентификатор сообщества в параметре owner_id необходимо указывать со знаком "-" — например, owner_id=-1 соответствует идентификатору сообщества ВКонтакте API (club1)
        # int (числовое значение), по умолчанию идентификатор текущего пользователя

        kwargs['owner_id'] = object.remote_owner_id

        # идентификатор объекта к которому оставлен комментарий.
        # напр 'video_id', 'photo_id'
        # int (числовое значение), обязательный параметр
        object_remote_field = '%s_id' % object.methods_namespace  # TODO: replace to RemoteManager.methods_namespace
        print object_remote_field
        print object.remote_id
        kwargs[object_remote_field] = object.remote_id

        # need_likes 1 — будет возвращено дополнительное поле likes. По умолчанию поле likes не возвращается.
        # флаг, может принимать значения 1 или 0
        kwargs['need_likes'] = int(need_likes)

        # sort порядок сортировки комментариев (asc — от старых к новым, desc - от новых к старым)
        # строка
        kwargs['sort'] = sort

        kwargs['extra_fields'] = {'object_id': object.pk, 'object_content_type': 20}

        return super(CommentRemoteManager, self).fetch(**kwargs)


class Comment(VkontakteModel, VkontakteCRUDModel):

    methods_namespace = 'video'
    #remote_pk_field = 'cid'
    fields_required_for_update = ['comment_id', 'owner_id']
    _commit_remote = False

    remote_id = models.CharField(
        u'ID', primary_key=True, max_length=20, help_text=u'Уникальный идентификатор', unique=True)

    #video = models.ForeignKey(Video, verbose_name=u'Видеозапись', related_name='comments')

    #object_content_type = models.ForeignKey(ContentType, related_name='comments')
    #object_id = models.PositiveIntegerField(db_index=True)
    object = generic.GenericForeignKey()  # 'object_content_type', 'object_id'

    author_content_type = models.ForeignKey(ContentType, related_name='video_comments')
    author_id = models.PositiveIntegerField(db_index=True)
    author = generic.GenericForeignKey('author_content_type', 'author_id')

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
        verbose_name = u'Комментарий видеозаписи Вконтакте'
        verbose_name_plural = u'Комментарии видеозаписей Вконтакте'

    @property
    def remote_owner_id(self):
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
            'owner_id': self.remote_owner_id,
            'video_id': self.object.remote_id,  # remote_id_short,
            'message': self.text,
#            'reply_to_comment': self.reply_for.id if self.reply_for else '',
            'from_group': int(from_group),
            'attachments': kwargs.get('attachments', ''),
        })
        return kwargs

    def prepare_update_params(self, **kwargs):
        kwargs.update({
            'owner_id': self.remote_owner_id,
            'comment_id': self.remote_id_short,
            'message': self.text,
            'attachments': kwargs.get('attachments', ''),
        })
        return kwargs

    def prepare_delete_params(self):
        return {
            'owner_id': self.remote_owner_id,
            'comment_id': self.remote_id_short
        }

    def parse_remote_id_from_response(self, response):
        if response:
            return '%s_%s' % (self.remote_owner_id, response)
        return None

    def get_or_create_group_or_user(self, remote_id):
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

        if '_' not in str(self.remote_id):
            self.remote_id = '%s_%s' % (self.remote_owner_id, self.remote_id)