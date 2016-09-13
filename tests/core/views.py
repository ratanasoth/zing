# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import json

import pytest

from django import forms
from django.http import Http404

from pytest_pootle.factories import LanguageDBFactory, UserFactory
from pytest_pootle.utils import create_api_request

from pootle.core.views import APIView
from accounts.models import User


class UserAPIView(APIView):
    model = User
    restrict_to_methods = ('get', 'delete',)
    page_size = 10
    fields = ('username', 'full_name',)


class WriteableUserAPIView(APIView):
    model = User
    fields = ('username', 'email',)


class UserSettingsForm(forms.ModelForm):

    password = forms.CharField(required=False)

    class Meta(object):
        model = User
        fields = ('username', 'password', 'full_name')
        widgets = {
            'password': forms.PasswordInput(),
        }

    def clean_password(self):
        return self.cleaned_data['password'].upper()


class WriteableUserSettingsAPIView(APIView):
    model = User
    edit_form_class = UserSettingsForm


class UserM2MAPIView(APIView):
    model = User
    restrict_to_methods = ('get', 'delete',)
    page_size = 10
    fields = ('username', 'alt_src_langs',)
    m2m = ('alt_src_langs', )


def test_apiview_invalid_method(rf):
    """Tests for invalid methods."""
    view = UserAPIView.as_view()

    # Forbidden method
    request = create_api_request(rf, 'post')
    response = view(request)

    # "Method not allowed" if the method is not within the restricted list
    assert response.status_code == 405

    # Non-existent method
    request = create_api_request(rf, 'patch')
    response = view(request)
    assert response.status_code == 405


@pytest.mark.django_db
def test_apiview_get_single(rf):
    """Tests retrieving a single object using the API."""
    view = UserAPIView.as_view()
    user = UserFactory.create(username='foo')

    request = create_api_request(rf)
    response = view(request, id=user.id)

    # This should have been a valid request...
    assert response.status_code == 200

    # ...and JSON-encoded, so should properly parse it
    response_data = json.loads(response.content)
    assert isinstance(response_data, dict)
    assert response_data['username'] == 'foo'
    assert 'email' not in response_data

    # Non-existent IDs should return 404
    with pytest.raises(Http404):
        view(request, id='777')


@pytest.mark.django_db
def test_apiview_get_multiple(rf, no_extra_users):
    """Tests retrieving multiple objects using the API."""
    view = UserAPIView.as_view()
    UserFactory.create(username='foo')

    request = create_api_request(rf)

    response = view(request)
    response_data = json.loads(response.content)

    # Response should contain a 1-item list
    assert response.status_code == 200
    assert isinstance(response_data, dict)
    assert 'count' in response_data
    assert 'models' in response_data
    assert len(response_data['models']) == User.objects.count()

    # Let's add more users
    UserFactory.create_batch(5)

    response = view(request)
    response_data = json.loads(response.content)

    assert response.status_code == 200
    assert isinstance(response_data, dict)
    assert 'count' in response_data
    assert 'models' in response_data
    assert len(response_data['models']) == User.objects.count()

    # Let's add even more users to test pagination
    UserFactory.create_batch(5)

    response = view(request)
    response_data = json.loads(response.content)

    # First page is full
    assert response.status_code == 200
    assert isinstance(response_data, dict)
    assert 'count' in response_data
    assert 'models' in response_data
    assert len(response_data['models']) == 10

    request = create_api_request(rf, url='/?p=2')
    response = view(request)
    response_data = json.loads(response.content)

    # Second page constains a single user
    assert response.status_code == 200
    assert isinstance(response_data, dict)
    assert 'count' in response_data
    assert 'models' in response_data
    assert len(response_data['models']) == User.objects.count() - 10


@pytest.mark.django_db
def test_apiview_post(rf):
    """Tests creating a new object using the API."""
    view = WriteableUserAPIView.as_view()

    # Malformed request, only JSON-encoded data is understood
    request = create_api_request(rf, 'post')
    response = view(request)
    response_data = json.loads(response.content)

    assert response.status_code == 400
    assert 'msg' in response_data
    assert response_data['msg'] == 'Invalid JSON data'

    # Not sending all required data fails validation
    missing_data = {
        'not_a_field': 'not a value',
    }
    request = create_api_request(rf, 'post', data=missing_data)
    response = view(request)
    response_data = json.loads(response.content)

    assert response.status_code == 400
    assert 'errors' in response_data

    # Sending all required data should create a new user
    data = {
        'username': 'foo',
        'email': 'foo@bar.tld',
    }
    request = create_api_request(rf, 'post', data=data)
    response = view(request)
    response_data = json.loads(response.content)

    assert response.status_code == 200
    assert response_data['username'] == 'foo'

    user = User.objects.latest('id')
    assert user.username == 'foo'

    # Trying to add the same user again should fail validation
    response = view(request)
    response_data = json.loads(response.content)

    assert response.status_code == 400
    assert 'errors' in response_data


@pytest.mark.django_db
def test_apiview_put(rf):
    """Tests updating an object using the API."""
    view = WriteableUserAPIView.as_view()
    user = UserFactory.create(username='foo')

    # Malformed request, only JSON-encoded data is understood
    request = create_api_request(rf, 'put')
    response = view(request, id=user.id)
    response_data = json.loads(response.content)

    assert response.status_code == 400
    assert response_data['msg'] == 'Invalid JSON data'

    # Update a field's data
    new_username = 'foo_new'
    update_data = {
        'username': new_username,
    }
    request = create_api_request(rf, 'put', data=update_data)

    # Requesting unknown resources is a 404
    with pytest.raises(Http404):
        view(request, id='11')

    # All fields must be submitted
    response = view(request, id=user.id)
    response_data = json.loads(response.content)

    assert response.status_code == 400
    assert 'errors' in response_data

    # Specify missing fields
    update_data.update({
        'email': user.email,
    })
    request = create_api_request(rf, 'put', data=update_data)

    response = view(request, id=user.id)
    response_data = json.loads(response.content)

    # Now all is ok
    assert response.status_code == 200
    assert response_data['username'] == new_username
    # Email shouldn't have changed
    assert response_data['email'] == user.email

    # View with a custom form
    update_data.update({
        'password': 'd34db33f',
    })
    view = WriteableUserSettingsAPIView.as_view()
    request = create_api_request(rf, 'put', data=update_data)

    response = view(request, id=user.id)
    response_data = json.loads(response.content)
    assert response.status_code == 200
    assert 'password' not in response_data


@pytest.mark.django_db
def test_apiview_delete(rf):
    """Tests deleting an object using the API."""
    view = UserAPIView.as_view()

    user = UserFactory.create(username='foo')

    # Delete is not supported for collections
    request = create_api_request(rf, 'delete')
    response = view(request)

    assert response.status_code == 405
    assert User.objects.filter(id=user.id).count() == 1

    # But it is supported for single items (specified by id):
    response = view(request, id=user.id)

    assert response.status_code == 200
    assert User.objects.filter(id=user.id).count() == 0

    # Should raise 404 if we try to access a deleted resource again:
    with pytest.raises(Http404):
        view(request, id=user.id)


@pytest.mark.django_db
def test_apiview_search(rf):
    """Tests filtering through a search query."""
    # Note that `UserAPIView` is configured to search in all defined fields,
    # which are `username` and `full_name`
    view = UserAPIView.as_view()

    # Let's create some users to search for
    UserFactory.create(username='foo', full_name='Foo Bar')
    UserFactory.create(username='foobar', full_name='Foo Bar')
    UserFactory.create(username='foobarbaz', full_name='Foo Bar')

    # `q=bar` should match 3 users (full names match)
    request = create_api_request(rf, url='/?q=bar')
    response = view(request)
    response_data = json.loads(response.content)

    assert response.status_code == 200
    assert len(response_data['models']) == 3

    # `q=baz` should match 1 user
    request = create_api_request(rf, url='/?q=baz')
    response = view(request)
    response_data = json.loads(response.content)

    assert response.status_code == 200
    assert len(response_data['models']) == 1

    # Searches are case insensitive; `q=BaZ` should match 1 user
    request = create_api_request(rf, url='/?q=BaZ')
    response = view(request)
    response_data = json.loads(response.content)

    assert response.status_code == 200
    assert len(response_data['models']) == 1


@pytest.mark.django_db
def test_view_gathered_context_data(rf, member):

    from pootle.core.views import PootleDetailView
    from pootle_project.models import Project
    from pootle.core.delegate import context_data
    from pootle.core.plugin import provider

    class DummyView(PootleDetailView):

        model = Project

        def get_object(self):
            return Project.objects.get(code="project0")

        def get_context_data(self, *args, **kwargs):
            return dict(foo="bar")

        @property
        def permission_context(self):
            return self.get_object().directory

    request = rf.get("foo")
    request.user = member
    view = DummyView.as_view()
    response = view(request)
    assert response.context_data == dict(foo="bar")

    @provider(context_data, sender=DummyView)
    def provide_context_data(sender, **kwargs):
        return dict(
            foo2="bar2",
            sender=sender,
            context=kwargs["context"],
            view=kwargs["view"])

    view = DummyView.as_view()
    response = view(request)
    assert response.context_data.pop("sender") == DummyView
    assert response.context_data.pop("context") is response.context_data
    assert isinstance(response.context_data.pop("view"), DummyView)
    assert sorted(response.context_data.items()) == [
        ("foo", "bar"), ("foo2", "bar2")]
    context_data.receivers = []


@pytest.mark.django_db
def test_apiview_get_single_m2m(rf):
    """Tests retrieving a single object with an m2m field using the API."""
    view = UserM2MAPIView.as_view()
    user = UserFactory.create(username='foo')

    request = create_api_request(rf)
    response = view(request, id=user.id)
    response_data = json.loads(response.content)
    assert response_data["alt_src_langs"] == []

    user.alt_src_langs.add(LanguageDBFactory(code="alt1"))
    user.alt_src_langs.add(LanguageDBFactory(code="alt2"))
    request = create_api_request(rf)
    response = view(request, id=user.id)
    response_data = json.loads(response.content)
    assert response_data["alt_src_langs"]
    assert (
        response_data["alt_src_langs"]
        == list(str(l) for l in user.alt_src_langs.values_list("pk", flat=True)))


@pytest.mark.django_db
def test_apiview_get_multi_m2m(rf):
    """Tests several objects with m2m fields using the API."""
    view = UserM2MAPIView.as_view()
    user0 = UserFactory.create(username='foo0')
    user1 = UserFactory.create(username='foo1')

    request = create_api_request(rf)
    response = view(request)
    response_data = json.loads(response.content)

    for model in [x for x in response_data["models"]
                  if x['username'] in ['foo0', 'foo1']]:
        assert model['alt_src_langs'] == []

    user0.alt_src_langs.add(LanguageDBFactory(code="alt1"))
    user0.alt_src_langs.add(LanguageDBFactory(code="alt2"))
    user1.alt_src_langs.add(LanguageDBFactory(code="alt3"))
    user1.alt_src_langs.add(LanguageDBFactory(code="alt4"))

    request = create_api_request(rf)
    response = view(request)
    response_data = json.loads(response.content)

    for model in response_data["models"]:
        user = User.objects.get(username=model["username"])
        if user in [user0, user1]:
            assert model["alt_src_langs"]
        assert (
            model["alt_src_langs"]
            == list(
                str(l) for l
                in user.alt_src_langs.values_list("pk", flat=True)))
