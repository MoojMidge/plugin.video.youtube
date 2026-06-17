# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from .request_client import YouTubeRequestClient
from ..youtube_exceptions import InvalidGrant, LoginException


class YouTubeLoginClient(YouTubeRequestClient):
    _AUTH_SERVER = 'https://oauth2.googleapis.com/'
    DEVICE_CODE_URL = _AUTH_SERVER + 'device/code'
    REVOKE_URL = _AUTH_SERVER + 'revoke'
    TOKEN_URL = _AUTH_SERVER + 'token'

    _AUTH_REQUEST_HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    TOKEN_TYPES_MAP = {}
    _configs = {}
    _access_tokens = {}
    _api_keys = {}
    for token_idx, client_type in enumerate(YouTubeRequestClient.CLIENT_TYPES):
        TOKEN_TYPES_MAP[token_idx] = client_type
        TOKEN_TYPES_MAP[client_type] = token_idx
        _configs[client_type] = {}
        _access_tokens[client_type] = None
        _api_keys[client_type] = None

    _initialised = False
    _logged_in = False

    def __init__(self,
                 configs=None,
                 access_tokens=None,
                 **kwargs):
        super(YouTubeLoginClient, self).__init__(
            exc_type=LoginException,
            **kwargs
        )
        YouTubeLoginClient.init(configs)
        self.set_access_token(access_tokens)
        self.initialised = any(self._configs.values())

    @classmethod
    def init(cls, configs=None, **_kwargs):
        if not configs:
            return

        _api_keys = cls._api_keys
        _configs = cls._configs
        for config_type, config in configs.items():
            if config_type not in _configs:
                continue
            config = _configs[config_type] = config or {}
            _api_keys[config_type] = config.get('key')

    def reinit(self, **kwargs):
        super(YouTubeLoginClient, self).reinit(**kwargs)

    @classmethod
    def convert_access_tokens(cls,
                              access_tokens=None,
                              to_dict=False,
                              to_list=False):
        if access_tokens is None:
            access_tokens = cls._access_tokens
        if to_dict or isinstance(access_tokens, (list, tuple)):
            access_tokens = {
                cls.TOKEN_TYPES_MAP[token_idx]: token
                for token_idx, token in enumerate(access_tokens)
                if token and token_idx in cls.TOKEN_TYPES_MAP
            }
        elif to_list or isinstance(access_tokens, dict):
            _access_tokens = [None] * len(cls.CLIENT_TYPES)
            for token_type, token in access_tokens.items():
                token_idx = cls.TOKEN_TYPES_MAP.get(token_type)
                if token_idx is None:
                    continue
                _access_tokens[token_idx] = token
            access_tokens = _access_tokens
        return access_tokens

    def set_access_token(self, access_tokens=None):
        existing_access_tokens = type(self)._access_tokens
        if access_tokens:
            if isinstance(access_tokens, (list, tuple)):
                access_tokens = self.convert_access_tokens(
                    access_tokens,
                    to_dict=True,
                )
            token_status = 0
            for token_type, token in existing_access_tokens.items():
                if token_type in access_tokens:
                    config = self._configs.get(token_type)
                    if config and config.get('token-allowed', True):
                        token = access_tokens[token_type]
                    else:
                        token = None
                else:
                    token = None
                existing_access_tokens[token_type] = token
                if token:
                    token_status |= 2
                elif token_type != 'dev':
                    token_status |= 1

            if token_status & 1:
                if token_status & 2:
                    self.logged_in = 'partially'
                else:
                    self.logged_in = False
            elif token_status & 2:
                self.logged_in = 'fully'
            else:
                self.logged_in = False
            self.log.info('User is %s logged in', self.logged_in or 'not')
        else:
            for token_type in existing_access_tokens:
                existing_access_tokens[token_type] = None
            self.logged_in = False
            self.log.info('User is not logged in')

    @property
    def initialised(self):
        return self._initialised

    @initialised.setter
    def initialised(self, value):
        type(self)._initialised = value

    @property
    def logged_in(self):
        return self._logged_in

    @logged_in.setter
    def logged_in(self, value):
        type(self)._logged_in = value

    @staticmethod
    def _login_error_hook(**kwargs):
        json_data = getattr(kwargs['exc'], 'json_data', None)
        if not json_data or 'error' not in json_data:
            return None, None, None, None, LoginException
        if json_data['error'] == 'authorization_pending':
            return None, None, None, json_data, False
        if (json_data['error'] == 'invalid_grant'
                and json_data.get('code') == 400):
            return None, None, None, json_data, InvalidGrant(json_data)
        return None, None, None, json_data, LoginException(json_data)

    def revoke(self, token):
        if not token:
            return

        # https://developers.google.com/youtube/v3/guides/auth/devices
        post_data = {
            'token': token,
        }

        self.request(
            self.REVOKE_URL,
            method='POST',
            data=post_data,
            headers=self._AUTH_REQUEST_HEADERS,
            response_hook=self._response_hook,
            event_hook_kwargs={'_json_response': True},
            error_hook=self._login_error_hook,
            error_title='Logout failed - Refresh token revocation error',
            raise_exc=True,
        )

    def refresh_token(self, token_type, refresh_token):
        if not refresh_token:
            return None

        login_type = self.TOKEN_TYPES_MAP.get(token_type)
        config = self._configs.get(login_type)
        if not config:
            return None

        client_id = config.get('id')
        client_secret = config.get('secret')
        if not client_id or not client_secret:
            return None

        # https://developers.google.com/youtube/v3/guides/auth/devices
        post_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }

        log_info = '{login_type} request: {log_params!p}'
        self.log.debug(
            log_info,
            login_type=login_type,
            log_params=post_data,
        )

        json_data = self.request(
            self.TOKEN_URL,
            method='POST',
            data=post_data,
            headers=self._AUTH_REQUEST_HEADERS,
            response_hook=self._response_hook,
            event_hook_kwargs={'_json_response': True},
            error_hook=self._login_error_hook,
            error_title='Login failed - Refresh token grant error',
            error_info=log_info,
            raise_exc=True,
            login_type=login_type,
            log_params=post_data,
        )
        return json_data

    def request_access_token(self, token_type, device_code):
        if not device_code:
            return None

        login_type = self.TOKEN_TYPES_MAP.get(token_type)
        config = self._configs.get(login_type)
        if not config:
            return None

        client_id = config.get('id')
        client_secret = config.get('secret')
        if not client_id or not client_secret:
            return None

        # https://developers.google.com/youtube/v3/guides/auth/devices
        post_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': device_code,
            'grant_type': 'http://oauth.net/grant_type/device/1.0',
        }

        log_info = '{login_type} request: {log_params!p}'
        self.log.debug(
            log_info,
            login_type=login_type,
            log_params=post_data,
        )

        json_data = self.request(
            self.TOKEN_URL,
            method='POST',
            data=post_data,
            headers=self._AUTH_REQUEST_HEADERS,
            response_hook=self._response_hook,
            event_hook_kwargs={'_json_response': True},
            error_hook=self._login_error_hook,
            error_title='Login failed - Access token request error',
            error_info=log_info,
            raise_exc=True,
            login_type=login_type,
            log_params=post_data,
        )
        return json_data

    def request_device_and_user_code(self, token_type):
        login_type = self.TOKEN_TYPES_MAP.get(token_type)
        config = self._configs.get(login_type)
        if not config:
            return None

        client_id = config.get('id')
        if not client_id:
            return None

        # https://developers.google.com/youtube/v3/guides/auth/devices
        post_data = {
            'client_id': client_id,
            'scope': 'https://www.googleapis.com/auth/youtube',
        }

        log_info = '{login_type} request: {log_params!p}'
        self.log.debug(
            log_info,
            login_type=login_type,
            log_params=post_data,
        )

        json_data = self.request(
            self.DEVICE_CODE_URL,
            method='POST',
            data=post_data,
            headers=self._AUTH_REQUEST_HEADERS,
            response_hook=self._response_hook,
            event_hook_kwargs={'_json_response': True},
            error_hook=self._login_error_hook,
            error_title='Login failed - Device/user code request error',
            error_info=log_info,
            raise_exc=True,
            login_type=login_type,
            log_params=post_data,
        )
        return json_data
