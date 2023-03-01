# Copyright (C) 2021-2023 tiksan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from mongoengine import DynamicDocument, IntField


class WithdrawalModel(DynamicDocument):
    wid = IntField(primary_key=True)  # The withdrawal ID
    factiontid = IntField()
    amount = IntField()
    requester = IntField()
    time_requested = IntField()
    fulfiller = IntField()  # 0: unfilled; -1: system; -tid: cancelled; tid: fulfilled
    time_fulfilled = IntField()
    withdrawal_message = IntField()
    wtype = IntField(default=0)  # 0: cash; 1: points
