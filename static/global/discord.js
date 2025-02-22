/* Copyright (C) 2021-2023 tiksan

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>. */

const guildid = document.currentScript.getAttribute("data-guildid");
const key = document.currentScript.getAttribute("data-key");

var discordRoles = null;
var discordChannels = null;
var serverConfig = null;

let rolesRequest = obj => {
    return new Promise((resolve, reject) => {
        let xhttp = new XMLHttpRequest();

        xhttp.onload = function() {
            let response = xhttp.response;
    
            if("code" in response) {
                generateToast("Discord Roles Not Located", response["message"]);
                reject();
                return;
            }
    
            discordRoles = response["roles"];
    
            $.each(response["roles"], function(role_id, role) {
                $(".discord-role-selector").append($("<option>", {
                    "value": role.id,
                    "text": role.name
                }));
            });
    
            // $(".discord-role-selector").selectpicker();
            resolve();
        }
        xhttp.responseType = "json";
        xhttp.open("GET", `/api/bot/server/${guildid}/roles`)
        xhttp.setRequestHeader("Authorization", `Basic ${btoa(`${key}:`)}`);
        xhttp.setRequestHeader("Content-Type", "application/json");

        if(guildid !== null && key !== null && $(".discord-role-selector").length !== 0) {
            xhttp.send();
        }
    })
}

let channelsRequest = obj => {
    return new Promise((resolve, reject) => {
        let xhttp = new XMLHttpRequest();

        xhttp.onload = function() {
            let response = xhttp.response;
    
            if("code" in response) {
                generateToast("Discord Channels Not Located", response["message"]);
                reject();
                return;
            }
    
            discordChannels = response["channels"];
    
            $.each(response["channels"], function(category_id, category) {
                $(".discord-channel-selector").append($("<optgroup>", {
                    "label": category.name,
                    "data-category-id": category["id"]
                }));
    
                $.each(category["channels"], function(channel_id, channel) {
                    $(`optgroup[data-category-id="${category["id"]}"]`).append($("<option>", {
                        "value": channel.id,
                        "text": `#${channel.name}`
                    }))
                })
            });
    
            // $(".discord-channel-selector").selectpicker();
            resolve();
        }
        xhttp.responseType = "json";
        xhttp.open("GET", `/api/bot/server/${guildid}/channels`)
        xhttp.setRequestHeader("Authorization", `Basic ${btoa(`${key}:`)}`);
        xhttp.setRequestHeader("Content-Type", "application/json");
    
        if(guildid !== null && key !== null && $(".discord-channel-selector").length !== 0) {
            xhttp.send();
        }
    })
}

let configRequest = obj => {
    return new Promise((resolve, reject) => {
        if(serverConfig !== null) {
            resolve();
        } else {
            let xhttp = new XMLHttpRequest();

            xhttp.onload = function() {
                let response = xhttp.response;

                if("code" in response) {
                    generateToast("Discord Config Not Located", response["message"]);
                    reject();
                    throw new Error("Config error");
                }

                serverConfig = xhttp.response;
                resolve();
            }

            xhttp.responseType = "json";
            xhttp.open("GET", `/api/bot/server/${guildid}`);
            xhttp.setRequestHeader("Authorization", `Basic ${btoa(`${key}:`)}`);
            xhttp.setRequestHeader("Content-Type", "application/json");
            xhttp.send();
        }
    });
}