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

import json
import logging

import requests
from flask import Blueprint, render_template, request
from flask_login import login_required

import tasks
import utils
from controllers.decorators import admin_required
from models.factionmodel import FactionModel
from models.servermodel import ServerModel
from models.usermodel import UserModel
from redisdb import get_redis
from tasks import faction as factiontasks
from tasks import guild as guildtasks
from tasks import stakeouts as stakeouttasks
from tasks import user as usertasks

mod = Blueprint("adminroutes", __name__)


@mod.route("/admin")
@login_required
@admin_required
def index():
    return render_template("admin/index.html")


@mod.route("/admin/dashboard", methods=["GET", "POST"])
@login_required
@admin_required
def dashboard():
    if request.method == "POST":
        if request.form.get("refreshfactions") is not None:
            factiontasks.refresh_factions.delay()
        elif request.form.get("refreshguilds") is not None:
            guildtasks.refresh_guilds.delay()
        elif request.form.get("refreshusers") is not None:
            usertasks.refresh_users.delay()
        elif request.form.get("fetchattacks") is not None:
            factiontasks.fetch_attacks_runner.delay()
        elif request.form.get("refreshuserstakeouts") is not None:
            stakeouttasks.user_stakeouts.delay()
        elif request.form.get("refreshfactionstakeouts") is not None:
            stakeouttasks.faction_stakeouts.delay()
        elif request.form.get("mailcheck") is not None:
            usertasks.mail_check.delay()
        elif request.form.get("purgecache") is not None:
            redis = get_redis()

            for key in redis.keys("tornium:torn-cache:*"):
                redis.delete(key)

            for key in redis.keys("tornium:discord:ratelimit:*"):
                redis.delete(key)
        elif request.form.get("updatecommands") is not None:
            with open("commands/commands.json") as commands_file:
                commands_list = json.load(commands_file)

            botlogger = logging.getLogger("skynet")
            botlogger.setLevel(logging.DEBUG)
            handler = logging.FileHandler(filename="skynet.log", encoding="utf-8", mode="a")
            handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
            botlogger.addHandler(handler)

            session = requests.Session()
            application_id = get_redis().get("tornium:settings:skynet:applicationid")
            botlogger.debug(application_id)

            commands_data = []

            for commandid in commands_list["active"]:
                with open(f"commands/{commandid}.json") as command_file:
                    command_json = json.load(command_file)
                    commands_data.append(command_json)

            botlogger.debug(commands_data)

            try:
                commands_data = tasks.discordput(
                    f"applications/{application_id}/commands",
                    commands_data,
                    session=session,
                )
                botlogger.info(commands_data)
            except utils.DiscordError as e:
                botlogger.error(e)
                raise e
            except Exception as e:
                botlogger.error(e)
                raise e

    return render_template("admin/dashboard.html")


@mod.route("/admin/database")
@login_required
@admin_required
def database():
    return render_template("admin/database.html")


@mod.route("/admin/database/faction")
@login_required
@admin_required
def faction_database():
    return render_template("admin/factiondb.html")


@mod.route("/admin/database/faction/<int:tid>")
@login_required
@admin_required
def faction(tid: int):
    return render_template("admin/faction.html", faction=FactionModel.objects(tid=tid).first())


@mod.route("/admin/database/factions")
@login_required
@admin_required
def factions():
    start = int(request.args.get("start"))
    length = int(request.args.get("length"))
    search_value = request.args.get("search[value]")

    factions = []

    if search_value is None:
        for faction in FactionModel.objects().all()[start : start + length]:
            factions.append([faction.tid, faction.name])
    else:
        for faction in FactionModel.objects(name__startswith=search_value)[start : start + length]:
            factions.append([faction.tid, faction.name])

    return {
        "draw": request.args.get("draw"),
        "recordsTotal": FactionModel.objects.count(),
        "recordsFiltered": FactionModel.objects.count(),
        "data": factions,
    }


@mod.route("/admin/database/user")
@login_required
@admin_required
def user_database():
    return render_template("admin/userdb.html")


@mod.route("/admin/database/user/<int:tid>")
@login_required
@admin_required
def user(tid: int):
    return render_template("admin/user.html", user=UserModel.objects(tid=tid).first())


@mod.route("/admin/database/users")
@login_required
@admin_required
def users():
    start = int(request.args.get("start"))
    length = int(request.args.get("length"))
    search_value = request.args.get("search[value]")

    users = []

    if search_value is None:
        for user in UserModel.objects().all()[start : start + length]:
            users.append([user.tid, user.name, user.discord_id if user.discord_id != 0 else ""])
    else:
        for user in UserModel.objects(name__startswith=search_value)[start : start + length]:
            users.append([user.tid, user.name, user.discord_id if user.discord_id != 0 else ""])

    return {
        "draw": request.args.get("draw"),
        "recordsTotal": UserModel.objects.count(),
        "recordsFiltered": UserModel.objects.count(),
        "data": users,
    }


@mod.route("/admin/database/server")
@login_required
@admin_required
def server_database():
    return render_template("admin/serverdb.html")


@mod.route("/admin/database/server/<int:did>")
@login_required
@admin_required
def server(did: int):
    return render_template("admin/server.html", server=ServerModel.objects(sid=did).first())


@mod.route("/admin/database/servers")
@login_required
@admin_required
def servers():
    start = int(request.args.get("start"))
    length = int(request.args.get("length"))
    search_value = request.args.get("search[value]")

    servers = []
    server: ServerModel

    if search_value is None:
        for server in ServerModel.objects().all()[start : start + length]:
            servers.append([str(server.sid), server.name])
    else:
        for server in ServerModel.objects(name__startswith=search_value).all()[start : start + length]:
            servers.append([str(server.sid), server.name])

    return {
        "draw": request.args.get("draw"),
        "recordsTotal": ServerModel.objects.count(),
        "recordsFiltered": ServerModel.objects.count(),
        "data": servers,
    }
