import logging
import idena.emoji as emo
import idena.utils as utl
import plotly.express as px

import io
import pandas as pd
import plotly.io as pio

from io import BytesIO

from datetime import datetime
from collections import OrderedDict
from idena.plugin import IdenaPlugin
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackQueryHandler


class Show(IdenaPlugin):

    _PREFIX = "show_"

    def __enter__(self):
        self.add_handler(CallbackQueryHandler(self._callback), group=0)
        return self

    def execute(self, bot, update, args):
        show_count = 3

        if len(args) == 1:
            try:
                show_count = int(args[0])
            except ValueError:
                update.message.reply_text(
                    f"{emo.ERROR} The argument needs to be an Integer. "
                    f"It represents the number of past votes to show",
                    parse_mode=ParseMode.MARKDOWN)
                return
        else:
            if len(args) > 1:
                update.message.reply_text(
                    self.get_usage(),
                    parse_mode=ParseMode.MARKDOWN)
                return

        sql = self.get_global_resource("select_votes.sql")
        res = self.execute_global_sql(sql)

        if not res["success"]:
            msg = f"{emo.ERROR} Not possible to list votes"
            update.message.reply_text(msg)
            self.notify(msg)
            return

        user_id = update.effective_user.id

        count = 1
        for data in reversed(res["data"]):
            if count > show_count:
                break

            bot.send_message(user_id, data[2], reply_markup=self._show_button(data[0]))
            count += 1

    def _show_button(self, row_id):
        data = f"{self._PREFIX}{row_id}"
        menu = utl.build_menu([InlineKeyboardButton("Show Results", callback_data=data)])
        return InlineKeyboardMarkup(menu, resize_keyboard=True)

    def _callback(self, bot, update):
        query = update.callback_query

        if not str(query.data).startswith(self._PREFIX):
            return

        vote_id = query.data.split("_")[1]

        sql = self.get_global_resource("select_vote.sql")
        res = self.execute_global_sql(sql, vote_id)

        if not res["success"]:
            msg = f"{emo.ERROR} Error reading vote"
            bot.answer_callback_query(query.id, msg)
            update.message.reply_text(f"{msg} {vote_id}")
            self.notify(f"{msg} {vote_id}")
            return

        result = {
            "topic": None,
            "ending": None,
            "total_votes": None,
            "options": OrderedDict()
        }

        vote_data = dict()
        for op in res["data"]:
            result["topic"] = op[2]
            result["ending"] = op[7]
            result["options"][op[4]] = list()

            if result["ending"]:
                dt = datetime.strptime(result["ending"], "%Y-%m-%d %H:%M:%S")

            for key, value in self.api.valid_trx_for(op[4]).items():
                if result["ending"]:
                    if value["timestamp"] > dt:
                        logging.info(f"Vote not counted. Too late: {key} {value}")
                        continue

                if key in vote_data:
                    if value["timestamp"] < vote_data[key]["timestamp"]:
                        logging.info(f"Vote not counted. New available: {key} {value}")
                        continue

                vote_data[key] = value

        logging.info(f"Votes: {vote_data}")

        total_votes = 0
        for key, value in vote_data.items():
            result["options"][value["option"]].append(key)
            total_votes += 1

        result["total_votes"] = total_votes

        logging.info(f"Result: {result}")

        data = {
            "Options": [],
            "Votes": []
        }

        count = 0
        for op, op_data in result["options"].items():
            op_str = res["data"][count][3]
            data["Options"].append(op_str)

            data["Votes"].append(len(op_data))
            count += 1

        fig = px.bar(
            pd.DataFrame(data=data),
            x="Options",
            y="Votes",
            title=result["topic"])

        """
        fig.update_yaxes(
            tickformat=',d'
        )
        """

        query.message.reply_photo(
            photo=io.BufferedReader(BytesIO(pio.to_image(fig, format="jpeg"))),
            quote=False)

        bot.answer_callback_query(query.id, str())
