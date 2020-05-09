import re
import uuid
import logging
import idena.emoji as emo
import idena.utils as utl
import plotly.express as px

import io
import pandas as pd
import plotly.io as pio

from enum import auto
from io import BytesIO
from datetime import datetime
from collections import OrderedDict
from idena.plugin import IdenaPlugin
from telegram import ReplyKeyboardMarkup, KeyboardButton, ParseMode, ReplyKeyboardRemove, Chat
from telegram.ext import RegexHandler, CommandHandler, ConversationHandler, MessageHandler, Filters


# TODO: Restrict to 7 options
# TODO: Restrict option to 100 chars
# TODO: Add periodic job that checks if vote is over (every minute) and if yes, sends result to admins
class Vote(IdenaPlugin):

    DATETIME_REGEX = r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})+$"

    QUESTION = auto()
    ENDDATE = auto()
    OPTION = auto()

    CANCEL = "Cancel"
    NO_END = "No End Date"
    FINISHED = "Finished"

    def __enter__(self):
        if not self.global_table_exists("options"):
            sql = self.get_global_resource("create_options.sql")
            self.execute_global_sql(sql)
        if not self.global_table_exists("votes"):
            sql = self.get_global_resource("create_votes.sql")
            self.execute_global_sql(sql)

        self.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler('vote', self.start)],
                states={
                    self.QUESTION:
                        [RegexHandler(f"^({self.CANCEL})$", self.cancel),
                         MessageHandler(Filters.text, self.question, pass_user_data=True)],
                    self.ENDDATE:
                        [RegexHandler(f"^({self.CANCEL})$", self.cancel),
                         RegexHandler(f"^({self.NO_END})$", self.option, pass_user_data=True),
                         MessageHandler(Filters.text, self.enddate, pass_user_data=True)],
                    self.OPTION:
                        [RegexHandler(f"^({self.CANCEL})$", self.cancel),
                         RegexHandler(f"^({self.FINISHED})$", self.finished, pass_user_data=True),
                         MessageHandler(Filters.text, self.option, pass_user_data=True)]
                },
                fallbacks=[CommandHandler('vote', self.question)],
                allow_reentry=True),
            group=1)

        return self

    @IdenaPlugin.private
    def start(self, bot, update):
        msg = "Let's create a vote. Send me the question."
        update.message.reply_text(msg, reply_markup=self.keyboard_cancel())

        return self.QUESTION

    def question(self, bot, update, user_data):
        user_data["question"] = update.message.text
        user_data["options"] = []
        user_data["end"] = None

        msg = "OK. If the vote should end at a specific date " \
              "and time then send it to me (YYYY-MM-DD HH:MM)"
        update.message.reply_text(msg, reply_markup=self.keyboard_datetime())

        return self.ENDDATE

    def enddate(self, bot, update, user_data):
        text = update.message.text

        if not re.compile(self.DATETIME_REGEX).match(text):
            update.message.reply_text(
                "Not a valid date-time. Format to use:\n`YYYY-MM-DD HH:MM`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.keyboard_datetime())

            return self.ENDDATE

        user_data["end"] = f"{text}:00"

        msg = "OK. Next I need the first option."
        update.message.reply_text(msg, reply_markup=self.keyboard_cancel())

        return self.OPTION

    def option(self, bot, update, user_data):
        text = update.message.text

        if text == self.NO_END:
            msg = "OK. Next I need the first option."
            update.message.reply_text(msg, reply_markup=self.keyboard_cancel())
        else:
            user_data["options"].append(text)
            msg = "Please send me the next option or press the 'Finished' button"
            update.message.reply_text(msg, reply_markup=self.keyboard_finished())

        return self.OPTION

    def cancel(self, bot, update):
        msg = f"{emo.CANCEL} New vote canceled"
        update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())

        return ConversationHandler.END

    def finished(self, bot, update, user_data):
        uid = str(uuid.uuid4().hex)
        usr = update.effective_user.id
        qst = user_data["question"]
        end = user_data["end"]

        # Insert vote into database
        sql = self.get_global_resource("insert_vote.sql")
        self.execute_global_sql(sql, uid, usr, qst, end)

        sql = self.get_global_resource("insert_option.sql")

        for option in user_data["options"]:
            wallet = utl.generate_eth_wallet()
            addr = wallet["address"]
            priv = wallet["privkey"]

            # Insert vote options into database
            self.execute_global_sql(sql, uid, option, addr, priv)

        link = f"https://t.me/{bot.name[1:]}?startgroup={uid}"
        msg = f"{emo.CHECK} DONE! [Forward this vote to a group]({link})"

        update.message.reply_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove())

        end = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()

        if end and now < end:
            self.repeat_job(self._post_results, 0, first=end, context=uid)

        return ConversationHandler.END

    def keyboard_cancel(self):
        menu = utl.build_menu([KeyboardButton(self.CANCEL)], n_cols=1)
        return ReplyKeyboardMarkup(menu, resize_keyboard=True)

    def keyboard_datetime(self):
        buttons = [
            KeyboardButton(self.CANCEL),
            KeyboardButton(self.NO_END)
        ]

        menu = utl.build_menu(buttons, n_cols=2)
        return ReplyKeyboardMarkup(menu, resize_keyboard=True)

    def keyboard_finished(self):
        buttons = [
            KeyboardButton(self.CANCEL),
            KeyboardButton(self.FINISHED)
        ]

        menu = utl.build_menu(buttons, n_cols=2)
        return ReplyKeyboardMarkup(menu, resize_keyboard=True)

    def _post_results(self, bot, job):
        job.schedule_removal()
        vote_id = job.context

        sql = self.get_global_resource("select_vote.sql")
        res = self.execute_global_sql(sql, vote_id)

        if not res["success"]:
            msg = f"{emo.ERROR} Error reading vote"
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

        if self.global_config.get("admin", "notify_on_error"):
            for admin in self.global_config.get("admin", "ids"):
                try:
                    bot.send_photo(
                        admin,
                        photo=io.BufferedReader(BytesIO(pio.to_image(fig, format="jpeg"))))
                    bot.send_message(
                        admin,
                        str(vote_data))
                except Exception as e:
                    error = f"Not possible to notify admin id '{admin}' about ended vote"
                    logging.error(f"{error}: {e}")

    def execute(self, bot, update, args):
        # We don't need this method since we already have a ConversationHandler
        pass
