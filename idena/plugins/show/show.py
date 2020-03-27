import re
import uuid
import idena.emoji as emo
import idena.utils as utl

from enum import auto
from idena.plugin import IdenaPlugin
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
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
            sql = self.get_resource("select_votes.sql")
            res = self.execute_sql(sql, plugin="vote")
        elif show_type == "proposals" or show_type == "p":
            sql = self.get_resource("select_proposals.sql")
            res = self.execute_sql(sql, plugin="proposals")
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
        menu = utl.build_menu([InlineKeyboardButton("Show Result", callback_data=data)])
        return InlineKeyboardMarkup(menu, resize_keyboard=True)

    def _callback(self, bot, update):
        query = update.callback_query

        if not str(query.data).startswith(self._PREFIX):
            return

        sql = self.get_resource("select_vote.sql")
        rid = str(query.data)[len(self._PREFIX):]
        res = self.execute_sql(sql, rid, plugin="vote")

        if not res["success"]:
            msg = f"{emo.ERROR} Error reading vote"
            bot.answer_callback_query(query.id, msg)
            update.message.reply_text(f"{msg} {rid}")
            self.notify(f"{msg} {rid}")
            return

        options = [option[3] for option in res["data"]]
        question = res["data"][0][2]

        msg = f"Executed"
        bot.answer_callback_query(query.id, msg)
