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

import datetime
import random

import redisdb
import tasks
import utils
from models.faction import Faction
from models.server import Server
from models.user import User
from models.usermodel import UserModel
from models.withdrawalmodel import WithdrawalModel
from skynet.skyutils import SKYNET_ERROR, get_admin_keys, get_faction_keys, invoker_exists


@invoker_exists
def withdraw(interaction, *args, **kwargs):
    print(interaction)

    if "guild_id" not in interaction:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Not Allowed",
                        "description": "This command can not be run in a DM (for now).",
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    server = Server(interaction["guild_id"])
    user: UserModel = kwargs["invoker"]

    if "options" not in interaction["data"]:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Withdrawal Request Failed",
                        "description": "No options were passed with the "
                        "request. The withdrawal amount option is required.",
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    # -1: default
    # 0: cash (default)
    # 1: points
    withdrawal_option = utils.find_list(interaction["data"]["options"], "name", "option")

    if withdrawal_option == -1:
        withdrawal_option = 0
    elif withdrawal_option[1]["value"] == "Cash":
        withdrawal_option = 0
    elif withdrawal_option[1]["value"] == "Points":
        withdrawal_option = 1
    else:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Withdrawal Request Failed",
                        "description": "An incorrect withdrawal type was passed.",
                        "color": SKYNET_ERROR,
                        "footer": {"text": f"Inputted withdrawal type: {withdrawal_option[1]['value']}"},
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    admin_keys = kwargs.get("admin_keys")

    if admin_keys is None:
        admin_keys = get_admin_keys(interaction)

    if len(admin_keys) == 0:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "No API Keys",
                        "description": "No API keys were found to be run for this command. Please sign into "
                        "Tornium or run this command in a server with signed-in admins.",
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    try:
        user: User = User(user.tid)
        user.refresh(key=random.choice(admin_keys))

        if user.factiontid == 0:
            user.refresh(key=random.choice(admin_keys), force=True)

            if user.factiontid == 0:
                return {
                    "type": 4,
                    "data": {
                        "embeds": [
                            {
                                "title": "Faction ID Error",
                                "description": f"The faction ID of {interaction['message']['user']['username']} is not "
                                f"set regardless of a force refresh.",
                                "color": SKYNET_ERROR,
                            }
                        ],
                        "flags": 64,  # Ephemeral
                    },
                }
    except utils.MissingKeyError:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "No API Key Available",
                        "description": "No Torn API key could be utilized for this request.",
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    client = redisdb.get_redis()

    if client.get(f"tornium:banking-ratelimit:{user.tid}") is not None:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Ratelimit Reached",
                        "description": f"You have reached the ratelimit on banking requests (once every minute). "
                        f"Please try again in {client.ttl(f'tornium:banking-ratelimit:{user.tid}')} seconds.",
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }
    else:
        client.set(f"tornium:banking-ratelimit:{user.tid}", 1)
        client.expire(f"tornium:banking-ratelimit:{user.tid}", 60)

    withdrawal_amount = utils.find_list(interaction["data"]["options"], "name", "amount")

    if withdrawal_amount == -1:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Illegal Parameters Passed",
                        "description": "No withdrawal amount was passed, but is required.",
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    withdrawal_amount = withdrawal_amount[1]["value"]

    if type(withdrawal_amount) == str:
        if withdrawal_amount.lower() == "all":
            withdrawal_amount = "all"
        else:
            withdrawal_amount = utils.text_to_num(withdrawal_amount)

    faction = Faction(user.factiontid)

    if user.factiontid not in server.factions:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Server Configuration Required",
                        "description": f"The server needs to be added to {faction.name}'s bot configuration and to the "
                        f"server. Please contact the server administrators to do this via "
                        f"[the dashboard](https://tornium.com).",
                        "color": SKYNET_ERROR,
                    }
                ]
            },
        }

    if (
        faction.vault_config.get("banking") in [0, None]
        or faction.vault_config.get("banker") in [0, None]
        or faction.config.get("vault") in [0, None]
    ):
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Server Configuration Required",
                        "description": f"The server needs to be added to {faction.name}'s bot configuration and to the "
                        f"server. Please contact the server administrators to do this via "
                        f"[the dashboard](https://tornium.com).",
                        "color": SKYNET_ERROR,
                    }
                ]
            },
        }

    aa_keys = get_faction_keys(interaction, faction)

    if len(aa_keys) == 0:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "No API Keys",
                        "description": "No AA API keys were found to be run for this command. Please sign into "
                        "Tornium or ask a faction AA member to sign into Tornium.",
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    try:
        faction_balances = tasks.tornget("faction/?selections=donations", random.choice(aa_keys))
    except utils.TornError as e:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Torn API Error",
                        "description": f'The Torn API has raised error code {e.code}: "{e.message}".',
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }
    except utils.NetworkingError as e:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "HTTP Error",
                        "description": f'The Torn API has returned an HTTP error {e.code}: "{e.message}".',
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    faction_balances = faction_balances["donations"]

    if str(user.tid) not in faction_balances:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Faction Error",
                        "description": (
                            f"{user.name} is not in {faction.name}'s donations list according to the Torn API. "
                            f"If you think that this is an error, please report this to the developers of this bot."
                        ),
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    if withdrawal_option == 1:
        withdrawal_option_str = "points_balance"
    else:
        withdrawal_option_str = "money_balance"

    if withdrawal_amount != "all" and withdrawal_amount > faction_balances[str(user.tid)][withdrawal_option_str]:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Not Enough",
                        "description": "You do not have enough of the requested currency in the faction vault.",
                        "fields": [
                            {"name": "Amount Requested", "value": withdrawal_amount},
                            {
                                "name": "Amount Available",
                                "value": faction_balances[str(user.tid)][withdrawal_option_str],
                            },
                        ],
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }
    elif withdrawal_amount == "all" and faction_balances[str(user.tid)][withdrawal_option_str] <= 0:
        return {
            "type": 4,
            "data": {
                "embeds": [
                    {
                        "title": "Not Enough",
                        "description": "You have requested all of your currency, but have zero or a negative vault "
                        "balance.",
                        "color": SKYNET_ERROR,
                    }
                ],
                "flags": 64,  # Ephemeral
            },
        }

    request_id = WithdrawalModel.objects().count()
    send_link = f"https://tornium.com/faction/banking/fulfill/{request_id}"

    if withdrawal_amount != "all":
        message_payload = {
            "content": f'<@&{faction.vault_config["banker"]}>',
            "embeds": [
                {
                    "title": f"Vault Request #{request_id}",
                    "description": f"{user.name} [{user.tid}] is requesting {utils.commas(withdrawal_amount)} "
                    f"in {'points' if withdrawal_option == 1 else 'cash'}"
                    f" from the faction vault. "
                    f"To fulfill this request, enter `?f {request_id}` in this channel.",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                }
            ],
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 2,
                            "style": 5,
                            "label": "Faction Vault",
                            "url": "https://www.torn.com/factions.php?step=your#/tab=controls&option=give-to-user",
                        },
                        {"type": 2, "style": 5, "label": "Fulfill", "url": send_link},
                        {
                            "type": 2,
                            "style": 3,
                            "label": "Fulfill Manually",
                            "custom_id": "faction:vault:fulfill",
                        },
                    ],
                }
            ],
        }
    else:
        message_payload = {
            "content": f'<@&{faction.vault_config["banker"]}>',
            "embeds": [
                {
                    "title": f"Vault Request #{request_id}",
                    "description": f"{user.name} [{user.tid}] is requesting "
                    f"{utils.commas(faction_balances[str(user.tid)][withdrawal_option_str])} in "
                    f"{'points' if withdrawal_option == 1 else 'cash'}"
                    f" from the faction vault. "
                    f"To fulfill this request, enter `?f {request_id}` in this channel.",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                }
            ],
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 2,
                            "style": 5,
                            "label": "Faction Vault",
                            "url": "https://www.torn.com/factions.php?step=your#/tab=controls&option=give-to-user",
                        },
                        {"type": 2, "style": 5, "label": "Fulfill", "url": send_link},
                        {
                            "type": 2,
                            "style": 3,
                            "label": "Fulfill Manually",
                            "custom_id": "faction:vault:fulfill",
                        },
                        {
                            "type": 2,
                            "style": 4,
                            "label": "Cancel",
                            "custom_id": "faction:vault:cancel",
                        },
                    ],
                }
            ],
        }

    message = tasks.discordpost(
        f'channels/{faction.vault_config["banking"]}/messages',
        payload=message_payload,
    )

    withdrawal = WithdrawalModel(
        wid=request_id,
        amount=withdrawal_amount
        if withdrawal_amount != "all"
        else faction_balances[str(user.tid)][withdrawal_option_str],
        requester=user.tid,
        factiontid=user.factiontid,
        time_requested=utils.now(),
        fulfiller=0,
        time_fulfilled=0,
        withdrawal_message=message["id"],
        wtype=withdrawal_option,
    )
    withdrawal.save()

    return {
        "type": 4,
        "data": {
            "embeds": [
                {
                    "title": f"Vault Request #{request_id}",
                    "description": "Your vault request has been forwarded to the faction leadership.",
                    "fields": [
                        {
                            "name": "Request Type",
                            "value": "Cash" if withdrawal_option == 0 else "Points",
                        },
                        {"name": "Amount Requested", "value": withdrawal_amount},
                    ],
                }
            ],
            "flags": 64,  # Ephemeral
        },
    }
