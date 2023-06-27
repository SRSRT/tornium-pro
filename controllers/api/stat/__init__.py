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

import math
import random
import time
import typing

from billiard.exceptions import TimeLimitExceeded
from flask import jsonify, request
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q
from tornium_celery.tasks.user import update_user
from tornium_commons.errors import NetworkingError, RatelimitError, TornError
from tornium_commons.models import FactionModel, StatModel, UserModel

from controllers.api.decorators import authentication_required, ratelimit
from controllers.api.utils import api_ratelimit_response, make_exception_response


@authentication_required
@ratelimit
def generate_chain_list(*args, **kwargs):
    key = f'tornium:ratelimit:{kwargs["user"].tid}'

    variance = request.args.get("variance") if request.args.get("variance") is not None else 0.01
    ff = request.args.get("ff") if request.args.get("ff") is not None else 3

    try:
        variance = float(variance)
        ff = float(ff)
    except ValueError:
        return make_exception_response(
            "1000", key, details={"message": "Illegal parameter type. Must be a float or integer."}
        )

    if float(variance) < 0 or float(variance) > 0.1:
        return make_exception_response(
            "1000",
            key,
            details={"message": "An invalid variance has been provided."},
        )
    elif float(ff) < 1 or float(ff) > 3:
        return make_exception_response(
            "1000",
            key,
            details={"message": "An invalid FF has been provided."},
        )
    elif kwargs["user"].battlescore == 0:
        return make_exception_response(
            "0000",
            key,
            details={"message": "User does not have a stat score stored in the database."},
        )

    ff = float(ff)
    variance = float(variance)

    if ff == 3:
        variance = 0

    # f = fair fight
    # v = variance
    # d = defender's stat score
    # a = attacker's stat score
    #
    # f +- v = 1 + 8/3 * d/a
    # 0.375 * a * (f +- v - 1) = d
    #
    # f = 11/3 is equal ratio of d/a
    # f = 17/5 is 9/10 ratio of d/a

    if ff == 3:
        stat_entries: QuerySet = StatModel.objects(
            (Q(globalstat=True) | Q(addedid=kwargs["user"].tid) | Q(addedfactiontid=kwargs["user"].factionid))
            & Q(battlescore__gte=(0.375 * kwargs["user"].battlescore * (ff - 1)))
            & Q(battlescore__lte=(0.375 * kwargs["user"].battlescore * 2.4))
        )
    else:
        stat_entries: QuerySet = StatModel.objects(
            (Q(globalstat=True) | Q(addedid=kwargs["user"].tid) | Q(addedfactiontid=kwargs["user"].factionid))
            & Q(battlescore__gte=(0.375 * kwargs["user"].battlescore * (ff - variance - 1)))
            & Q(battlescore__lte=(0.375 * kwargs["user"].battlescore * (ff + variance - 1)))
        )

    stat_entries: list = list(set(stat_entries.all().values_list("tid")))
    jsonified_stat_entries = []
    targets = {}

    for stat_entry in stat_entries:
        stat: StatModel = (
            StatModel.objects(
                Q(tid=stat_entry)
                & (Q(globalstat=True) | Q(addedid=kwargs["user"].tid) | Q(addedfactiontid=kwargs["user"].factionid))
            )
            .order_by("-timeadded")
            .first()
        )

        if stat.battlescore > kwargs["user"].battlescore:
            continue

        if stat_entry in targets:
            target = targets[stat_entry]
        else:
            target: typing.Optional[UserModel] = UserModel.objects(tid=stat.tid).first()

            if target is None:
                try:
                    update_user(kwargs["user"].key, tid=stat.tid)
                except Exception as e:
                    print(e)

                continue

            targets[stat_entry] = target

        target_ff = round(1 + 8 / 3 * (stat.battlescore / kwargs["user"].battlescore), 2)

        if target_ff > 3:
            target_ff = 3
        if target is None or target.level == 0:
            continue

        try:
            base_respect = round((math.log(target.level) + 1) / 4, 2)
        except ValueError:
            continue

        jsonified_stat_entries.append(
            {
                "statid": str(stat.id),
                "tid": stat.tid,
                "battlescore": stat.battlescore,
                "timeadded": stat.timeadded,
                "ff": target_ff,
                "respect": round(base_respect * target_ff, 2),
                "user": {
                    "tid": target.tid,
                    "name": target.name,
                    "username": f"{target.name} [{target.tid}]",
                    "level": target.level,
                    "last_refresh": target.last_refresh,
                    "factionid": target.factionid,
                    "status": target.status,
                    "last_action": target.last_action,
                },
            }
        )

    return (
        jsonify(
            {
                "ff": ff,
                "variance": variance,
                "data": jsonified_stat_entries,
            }
        ),
        200,
        api_ratelimit_response(key),
    )


@authentication_required
@ratelimit
def get_stat_user(tid, *args, **kwargs):
    key = f'tornium:ratelimit:{kwargs["user"].tid}'

    stat_entries: QuerySet = (
        StatModel.objects(
            Q(tid=tid)
            & (Q(globalstat=True) | Q(addedid=kwargs["user"].tid) | Q(addedfactiontid=kwargs["user"].factionid))
        )
        .order_by("-timeadded")
        .exclude("tid")
        .all()
    )

    data = {"user": {}, "stat_entries": {}}

    update_user(kwargs["user"].key, tid=tid).get()
    user: UserModel = UserModel.objects(tid=tid).no_cache().first()

    if user is None:
        return make_exception_response("1100", key)

    if user.factionid != 0:
        faction = FactionModel.objects(tid=user.factionid).first()
    else:
        faction = None

    data["user"] = {
        "tid": user.tid,
        "name": user.name,
        "level": user.level,
        "last_refresh": user.last_refresh,
        "discord_id": user.discord_id,
        "faction": {"tid": faction.tid, "name": faction.name} if faction is not None else {"tid": 0, "name": "None"},
        "status": user.status,
        "last_action": user.last_action,
    }

    stat_entry: StatModel
    for stat_entry in stat_entries:
        data["stat_entries"][str(stat_entry.id)] = {
            "stat_score": stat_entry.battlescore,
            "timeadded": stat_entry.timeadded,
            "globalstat": stat_entry.globalstat,
        }

    return (jsonify(data), 200, api_ratelimit_response(key))
