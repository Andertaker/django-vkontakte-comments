# -*- coding: utf-8 -*-
from django.contrib import admin
from vkontakte_api.admin import VkontakteModelAdmin
from .models import Comment


class CommentAdmin(VkontakteModelAdmin):
    list_display = ('remote_id', 'object_id', 'author_id', 'text', 'date')
    list_filter = ('object_id',)


admin.site.register(Comment, CommentAdmin)
