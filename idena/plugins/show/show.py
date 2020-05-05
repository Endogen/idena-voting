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
    _TYPE_VOTE = "votes"
    _TYPE_PROPOSAL = "proposals"

    show_count = 3

    def __enter__(self):
        self.add_handler(CallbackQueryHandler(self._callback), group=0)
        return self

    def execute(self, bot, update, args):
        if len(args) == 2:
            try:
                self.show_count = int(args[1])
            except ValueError:
                update.message.reply_text(
                    f"{emo.ERROR} Second command argument needs to be an Integer. "
                    f"It represents the number of past votes to show",
                    parse_mode=ParseMode.MARKDOWN)
                return
        else:
            if not len(args) == 1:
                update.message.reply_text(
                    self.get_usage(),
                    parse_mode=ParseMode.MARKDOWN)
                return

        show_type = args[0].lower()

        if show_type == self._TYPE_VOTE:
            sql = self.get_global_resource("select_votes.sql")
            res = self.execute_global_sql(sql)
        elif show_type == self._TYPE_PROPOSAL:
            sql = self.get_global_resource("select_proposals.sql")
            res = self.execute_global_sql(sql)
        else:
            update.message.reply_text(
                self.get_usage(),
                parse_mode=ParseMode.MARKDOWN)
            return

        if not res["success"]:
            msg = f"{emo.ERROR} Not possible to show {show_type}"
            update.message.reply_text(msg)
            self.notify(msg)
            return

        user_id = update.effective_user.id

        count = 1
        for data in reversed(res["data"]):
            if count > self.show_count:
                break

            bot.send_message(user_id, data[2], reply_markup=self._show_button(show_type, data[0]))
            count += 1

    def _show_button(self, show_type, row_id):
        data = f"{self._PREFIX}{show_type}_{row_id}"
        menu = utl.build_menu([InlineKeyboardButton("Show Results", callback_data=data)])
        return InlineKeyboardMarkup(menu, resize_keyboard=True)

    def _callback(self, bot, update):
        query = update.callback_query

        if not str(query.data).startswith(self._PREFIX):
            return

        show_lst = query.data.split("_")
        show_type = show_lst[1]
        vote_id = show_lst[2]

        # --- VOTE ---
        if show_type == self._TYPE_VOTE:
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
                        if int(value["timestamp"]) > int(dt.replace().timestamp()):
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

        # --- PROPOSAL ---
        if show_type == self._TYPE_PROPOSAL:
            # TODO: Implement
            pass
