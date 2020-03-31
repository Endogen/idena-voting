import logging
import idena.emoji as emo
import idena.utils as utl
import plotly.graph_objects as go
import plotly.express as px

import io
import plotly
import pandas as pd
import plotly.io as pio

from io import BytesIO
from pandas import DataFrame

from idena.plugin import IdenaPlugin
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackQueryHandler


class Show(IdenaPlugin):

    _PREFIX = "show_"

    def __enter__(self):
        self.add_handler(CallbackQueryHandler(self._callback), group=0)
        return self

    def execute(self, bot, update, args):
        if not len(args) == 1:
            update.message.reply_text(
                self.get_usage(),
                parse_mode=ParseMode.MARKDOWN)
            return

        show_type = args[0].lower()

        if show_type == "votes" or show_type == "v":
            sql = self.get_global_resource("select_votes.sql")
            res = self.execute_global_sql(sql)
        elif show_type == "proposals" or show_type == "p":
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

        for data in res["data"]:
            bot.send_message(user_id, data[2], reply_markup=self._show_button(data[0]))

    def _show_button(self, row_id):
        data = f"show_{row_id}"
        menu = utl.build_menu([InlineKeyboardButton("Show Results", callback_data=data)])
        return InlineKeyboardMarkup(menu, resize_keyboard=True)

    def _callback(self, bot, update):
        query = update.callback_query

        if not str(query.data).startswith(self._PREFIX):
            return

        sql = self.get_global_resource("select_vote.sql")
        rid = str(query.data)[len(self._PREFIX):]
        res = self.execute_global_sql(sql, rid)

        if not res["success"]:
            msg = f"{emo.ERROR} Error reading vote"
            bot.answer_callback_query(query.id, msg)
            update.message.reply_text(f"{msg} {rid}")
            self.notify(f"{msg} {rid}")
            return

        total_votes = 0
        vote_data = list()
        for op in res["data"]:
            votes = self.api.valid_trx_for(op[4])
            vote_data.append(votes)
            total_votes += votes

        counter = 0
        for op in res["data"]:
            votes = vote_data[counter]
            counter += 1

        print("Vote data:", vote_data)

        options = [option[3] for option in res["data"]]
        question = res["data"][0][2]

        print("Options:", options)
        print("Question:", question)

        data_canada = px.data.gapminder().query("country == 'Canada'")
        fig = px.bar(data_canada, x='year', y='pop')
        #fig.show()

        update.message.reply_photo(
            photo=io.BufferedReader(BytesIO(pio.to_image(fig, format="jpeg"))),
            quote=False)

        msg = f"Executed"
        bot.answer_callback_query(query.id, msg)
