# -*- coding: utf-8 -*-
import logging

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from vkontakte_api.decorators import fetch_all, atomic
from vkontakte_api.mixins import CountOffsetManagerMixin, AfterBeforeManagerMixin, OwnerableModelMixin, \
    AuthorableModelMixin, LikableModelMixin, get_or_create_group_or_user
from vkontakte_api.models import VkontakteIDStrModel, VkontakteCRUDModel, VkontakteCRUDManager
from vkontakte_users.models import User


log = logging.getLogger('vkontakte_comments')


def get_method(object):
    namespace = get_methods_namespace(object)
    if namespace in ['video', 'photos', 'notes']:
        return 'createComment'
    elif namespace in ['wall', 'board']:
        return 'addComment'


def get_methods_namespace(object):
    return object.methods_namespace or object.__class__.remote.methods_namespace


class CommentRemoteManager(CountOffsetManagerMixin, AfterBeforeManagerMixin):

    @atomic
    @fetch_all(default_count=100)
    def fetch_album(self, album, sort='asc', need_likes=True, **kwargs):
        raise NotImplementedError

    @atomic
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
        kwargs[object.comments_remote_related_name] = object.remote_id_short

        # need_likes 1 — будет возвращено дополнительное поле likes. По умолчанию поле likes не возвращается.
        # флаг, может принимать значения 1 или 0
        kwargs['need_likes'] = int(need_likes)

        # sort порядок сортировки комментариев (asc — от старых к новым, desc - от новых к старым)
        # строка
        kwargs['sort'] = sort

        kwargs['extra_fields'] = {
            'object': object,
            'owner': object.owner,
        }

        return self.fetch(**kwargs)


class Comment(OwnerableModelMixin, AuthorableModelMixin, LikableModelMixin, VkontakteIDStrModel, VkontakteCRUDModel):

    fields_required_for_update = ['comment_id', 'owner_id', 'methods_namespace']
    likes_remote_type = 'comment'
    _commit_remote = False

    # if primary_key=True, impossible delete all comments:
    # ValueError: invalid literal for int() with base 10: '-16297716_137668'
#    remote_id = models.CharField(u'ID', max_length=20, help_text=u'Уникальный идентификатор', unique=True)

    object_content_type = models.ForeignKey(ContentType, related_name='content_type_objects_vkontakte_comments')
    object_id = models.BigIntegerField(db_index=True)
    object = generic.GenericForeignKey('object_content_type', 'object_id')

    date = models.DateTimeField(help_text=u'Дата создания', db_index=True)
    text = models.TextField(u'Текст сообщения')
    # attachments - присутствует только если у сообщения есть прикрепления,
    # содержит массив объектов (фотографии, ссылки и т.п.). Более подробная
    # информация представлена на странице Описание поля attachments
    attachments = models.TextField(u'Вложения')

    reply_for_content_type = models.ForeignKey(ContentType, null=True, related_name='replies')
    reply_for_id = models.BigIntegerField(null=True, db_index=True)
    reply_for = generic.GenericForeignKey('reply_for_content_type', 'reply_for_id')

    reply_to = models.ForeignKey('self', null=True, verbose_name=u'Это ответ на комментарий')

    objects = VkontakteCRUDManager()
    remote = CommentRemoteManager(remote_pk=('remote_id',), version=5.27, methods={
        'get': 'getComments',
        # commented becouse for some namespaces method is createComment
#       'create': 'addComment',
        'update': 'editComment',
        'delete': 'deleteComment',
        'restore': 'restoreComment',
    })

    class Meta:
        verbose_name = u'Комментарий Вконтакте'
        verbose_name_plural = u'Комментарии Вконтакте'

    @property
    def slug_prefix(self):
        return get_methods_namespace(self.object)

    def prepare_create_params(self, from_group=False, **kwargs):
        if self.author == self.object.owner and self.author_content_type.model == 'group':
            from_group = True
        kwargs.update({
            'owner_id': self.object.owner_remote_id,
            'message': self.text,  # video
            'text': self.text,  # wall
#            'reply_to_comment': self.reply_for.id if self.reply_for else '',
            'from_group': int(from_group),
            'attachments': kwargs.get('attachments', ''),
            'method': get_method(self.object),
            'methods_namespace': get_methods_namespace(self.object),
            self.object.comments_remote_related_name: self.object.remote_id_short,
        })
        return kwargs

    def prepare_update_params(self, **kwargs):
        kwargs.update({
            'owner_id': self.object.owner_remote_id,
            'comment_id': self.remote_id_short,
            'message': self.text,  # video
            'text': self.text,  # wall
            'attachments': kwargs.get('attachments', ''),
            'methods_namespace': get_methods_namespace(self.object),
        })
        return kwargs

    def prepare_delete_params(self):
        return {
            'owner_id': self.object.owner_remote_id,
            'comment_id': self.remote_id_short,
            'methods_namespace': get_methods_namespace(self.object),
        }

    def parse_remote_id_from_response(self, response):
        id = None
        if isinstance(response, int):
            id = response
        elif isinstance(response, dict):
            for field in ['id', 'cid', 'comment_id']:
                if field in response:
                    id = response[field]
                    break
        if id is None:
            raise ValueError('No comment ID found in response: %s' % response)
        return '%s_%s' % (self.object.owner_remote_id, id)

    def parse(self, response):
        # undocummented feature of API. if from_id == 101 -> comment by group
        if response['from_id'] == 101:
            self.author = self.object.owner
        else:
            self.author = get_or_create_group_or_user(response.pop('from_id'))

        # TODO: May be this field does not exists in late versions of API
        if 'poll' in response:
            response.pop('poll')

        if 'message' in response:
            response['text'] = response.pop('message')

        super(Comment, self).parse(response)
        if 'object' in self.__dict__:
            self.object = self.__dict__['object']  # TODO: check is it should be already saved or not

        if '_' not in str(self.remote_id):
            self.remote_id = '%s_%s' % (self.object.owner_remote_id, self.remote_id)

        if 'reply_to_uid' in response:
            self.reply_for = User.objects.get_or_create(remote_id=response['reply_to_uid'])[0]
        if 'reply_to_cid' in response:
            try:
                self.reply_to = Comment.objects.get(remote_id=response['reply_to_cid'])
            except:
                pass
