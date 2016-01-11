# -*- coding: utf-8 -*-
import json

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
import mock
from vkontakte_groups.factories import GroupFactory
from vkontakte_users.factories import UserFactory, User
from vkontakte_video.factories import AlbumFactory, VideoFactory, Album, Video
from vkontakte_wall.factories import PostFactory

from . models import Comment

GROUP_ID = 16297716  # https://vk.com/cocacola
ALBUM_ID = 50850761  # 9 videos
VIDEO_ID = 166742757  # 12 comments

GROUP_CRUD_ID = 59154616  # https://vk.com/club59154616 # django-vkontakte-wall crud operations
ALBUM_CRUD_ID = 55964907
VIDEO_CRUD_ID = 170947024
#USER_AUTHOR_ID = 201164356

POST_CRUD_ID = '-59154616_366'
USER_AUTHOR_ID = 201164356


class VkontakteCommentsTest(TestCase):

    def setUp(self):
        self.objects_to_delete = []

    def tearDown(self):
        for object in self.objects_to_delete:
            object.delete(commit_remote=True)

    def assertCommentTheSameEverywhere(self, comment):
        comment_remote = Comment.remote.fetch_by_object(object=comment.object).get(remote_id=comment.remote_id)
        self.assertEqual(comment_remote.remote_id, comment.remote_id)
        self.assertEqual(comment_remote.text, comment.text)
        self.assertEqual(comment_remote.author, comment.author)

    def assertNoCommentsForObject(self, object):
        # try to delete comments from prev tests
        for comment in Comment.remote.fetch_by_object(object=object):
            comment.delete(commit_remote=True)
        # checks there is no remote and local comments
        comments = Comment.remote.fetch_by_object(object=object)
        self.assertEqual(comments.count(), 0, 'Error: There are %s comments from previous test. Delete them manually here %s' % (
            comments.count(), object.get_url()))

    if 'vkontakte_video' in settings.INSTALLED_APPS:

        @mock.patch('vkontakte_users.models.User.remote.fetch', side_effect=lambda ids, **kw: User.objects.filter(id__in=[user.id for user in [UserFactory.create(remote_id=i) for i in ids]]))
        def test_video_fetch_comments(self, *kwargs):

            owner = GroupFactory(remote_id=GROUP_ID)
            #album = AlbumFactory(remote_id=ALBUM_ID, owner=owner)
            # not factory coz we need video.comments_count later
            video = Video.remote.fetch(owner=owner, ids=[VIDEO_ID])[0]

            comments = video.fetch_comments(count=10, sort='desc')
            self.assertEqual(len(comments), video.comments.count())
            self.assertEqual(len(comments), 10)

            # testing `after` parameter
            after = Comment.objects.order_by('-date')[2].date

            Comment.objects.all().delete()
            self.assertEqual(Comment.objects.count(), 0)

            comments = video.fetch_comments(after=after, sort='desc')
            self.assertEqual(len(comments), Comment.objects.count())
            self.assertEqual(len(comments), video.comments.count())
            self.assertEqual(len(comments), 3)

            date = comments[0].date
            self.assertGreaterEqual(date, after)

            # testing `all` parameter
            Comment.objects.all().delete()
            self.assertEqual(Comment.objects.count(), 0)

            comments = video.fetch_comments(all=True)
            self.assertEqual(len(comments), Comment.objects.count())
            self.assertEqual(len(comments), video.comments.count())
            self.assertEqual(len(comments), video.comments_count)
            self.assertTrue(video.comments.count() > 10)

        def test_fetch_by_user_parameter(self):
            user = UserFactory(remote_id=13312307)
            album = AlbumFactory(remote_id=55976289, owner=user)
            video = VideoFactory(remote_id=165144348, album=album, owner=user)

            comments = video.fetch_comments()
            self.assertGreater(len(comments), 0)
            self.assertEqual(Comment.objects.count(), len(comments))
            self.assertEqual(comments[0].object, video)
            self.assertEqual(comments[0].author, user)

        def test_fetch_with_count_and_offset(self):
            # testing `count` parameter, count is the same as limit
            owner = GroupFactory(remote_id=GROUP_ID)
            album = AlbumFactory(remote_id=ALBUM_ID, owner=owner)
            video = VideoFactory(remote_id=VIDEO_ID, album=album, owner=owner)

            self.assertEqual(Comment.objects.count(), 0)

            comments = video.fetch_comments(count=5)

            self.assertEqual(len(comments), 5)
            self.assertEqual(Comment.objects.count(), 5)

            # testing `offset` parameter
            comments2 = video.fetch_comments(count=2, offset=4)

            self.assertEqual(len(comments2), 2)
            self.assertEqual(Comment.objects.count(), 6)

            self.assertEqual(comments[4].remote_id, comments2[0].remote_id)

        def test_parse_comment(self):

            response = u'''{"date": 1387304612,
                "text": "Даёшь \\"Байкал\\"!!!!",
                "likes": {"count": 0, "can_like": 1, "user_likes": 0},
                "id": 811,
                "from_id": 27224390}
            '''

            owner = GroupFactory(remote_id=GROUP_ID)
            album = AlbumFactory(remote_id=ALBUM_ID, owner=owner)
            video = VideoFactory(remote_id=VIDEO_ID, album=album, owner=owner)

            comment = Comment(object=video)
            comment.parse(json.loads(response))
            comment.save()

            self.assertEqual(comment.remote_id, '-%s_811' % GROUP_ID)
            self.assertEqual(comment.object, video)
            self.assertEqual(comment.author.remote_id, 27224390)
            self.assertEqual(comment.text, u'Даёшь "Байкал"!!!!')
            self.assertIsNotNone(comment.date)

        def test_comment_video_crud_methods(self):
            owner = GroupFactory(remote_id=GROUP_CRUD_ID)
            album = AlbumFactory(remote_id=ALBUM_CRUD_ID, owner=owner)
            video = VideoFactory(remote_id=VIDEO_CRUD_ID, album=album, owner=owner)

            self.assertNoCommentsForObject(video)

            # create
            comment = Comment(text='Test comment', object=video, author=owner, date=timezone.now())
            comment.save(commit_remote=True)
            self.objects_to_delete += [comment]

            self.assertEqual(Comment.objects.count(), 1)
            self.assertEqual(comment.author, owner)
            self.assertNotEqual(len(comment.remote_id), 0)
            self.assertCommentTheSameEverywhere(comment)

            # create by manager
            comment = Comment.objects.create(
                text='Test comment created by manager', object=video, author=owner, date=timezone.now(), commit_remote=True)
            self.objects_to_delete += [comment]
            self.assertEqual(Comment.objects.count(), 2)

            self.assertEqual(Comment.objects.count(), 2)
            self.assertEqual(comment.author, owner)
            self.assertNotEqual(len(comment.remote_id), 0)
            self.assertCommentTheSameEverywhere(comment)

            # update
            comment.text = 'Test comment updated'
            comment.save(commit_remote=True)

            self.assertEqual(Comment.objects.count(), 2)
            self.assertCommentTheSameEverywhere(comment)

            # delete
            comment.delete(commit_remote=True)

            self.assertEqual(Comment.objects.count(), 2)
            self.assertTrue(comment.archived)
            self.assertEqual(Comment.remote.fetch_by_object(
                object=comment.object).filter(remote_id=comment.remote_id).count(), 0)

            # restore
            comment.restore(commit_remote=True)
            self.assertFalse(comment.archived)

            self.assertEqual(Comment.objects.count(), 2)
            self.assertCommentTheSameEverywhere(comment)

    if 'vkontakte_wall' in settings.INSTALLED_APPS:

        def test_comment_wall_crud_methods(self):
            group = GroupFactory(remote_id=GROUP_CRUD_ID)
            post = PostFactory(remote_id=POST_CRUD_ID, text='', owner=group)
            user = UserFactory(remote_id=USER_AUTHOR_ID)

            self.assertNoCommentsForObject(post)

            # create
            Comment.remote.fetch_by_object(object=post)
            self.assertEqual(Comment.objects.count(), 0)

            # create
            comment = Comment(text='Test comment', object=post, owner=group, author=user, date=timezone.now())
            comment.save(commit_remote=True)
            self.objects_to_delete += [comment]

            self.assertEqual(Comment.objects.count(), 1)
            self.assertNotEqual(len(comment.remote_id), 0)
            self.assertCommentTheSameEverywhere(comment)

            # create by manager
            comment = Comment.objects.create(
                text='Test comment created by manager', object=post, owner=group, author=user, date=timezone.now(), commit_remote=True)
            self.objects_to_delete += [comment]

            self.assertEqual(Comment.objects.count(), 2)
            self.assertNotEqual(len(comment.remote_id), 0)
            self.assertCommentTheSameEverywhere(comment)

            # update
            comment.text = 'Test comment updated'
            comment.save(commit_remote=True)

            self.assertEqual(Comment.objects.count(), 2)
            self.assertCommentTheSameEverywhere(comment)

            # delete
            comment.delete(commit_remote=True)

            self.assertEqual(Comment.objects.count(), 2)
            self.assertTrue(comment.archived)
            self.assertEqual(Comment.remote.fetch_by_object(
                object=comment.object).filter(remote_id=comment.remote_id).count(), 0)

            # restore
            comment.restore(commit_remote=True)
            self.assertFalse(comment.archived)

            self.assertEqual(Comment.objects.count(), 2)
            self.assertCommentTheSameEverywhere(comment)
