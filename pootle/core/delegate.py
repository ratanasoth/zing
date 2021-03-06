# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
# Copyright (C) Zing contributors.
#
# This file is a part of the Zing project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.


from pootle.core.plugin.delegate import Getter, Provider


search_backend = Getter(providing_args=["instance"])
contributors = Getter()

# view.context_data
context_data = Provider(providing_args=["view", "context"])
