import re
import uuid
import idena.emoji as emo
import idena.utils as utl

from enum import auto
from idena.plugin import IdenaPlugin
from telegram import ReplyKeyboardMarkup, KeyboardButton, ParseMode, ReplyKeyboardRemove
from telegram.ext import RegexHandler, CommandHandler, ConversationHandler, MessageHandler, Filters


# TODO: Add possibility to list current vote and see older votes?
class Vote(IdenaPlugin):

    DATETIME_REGEX = r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})+$"

    QUESTION = auto()
    ENDDATE = auto()
    OPTION = auto()

    CANCEL = "Cancel"
    NO_END = "No End Date"
    FINISHED = "Finished"

    def __enter__(self):
        if not self.table_exists("options"):
            sql = self.get_resource("create_options.sql")
            self.execute_sql(sql)
        if not self.table_exists("votes"):
            sql = self.get_resource("create_votes.sql")
            self.execute_sql(sql)

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
        sql = self.get_resource("insert_vote.sql")
        self.execute_sql(sql, uid, usr, qst, end)

        sql = self.get_resource("insert_option.sql")

        for option in user_data["options"]:
            wallet = utl.generate_eth_wallet()
            addr = wallet["address"]
            priv = wallet["privkey"]

            # Insert vote options into database
            self.execute_sql(sql, uid, option, addr, priv)

        link = f"https://t.me/{bot.name[1:]}?startgroup={self.get_name()}_{uid}"
        msg = f"{emo.CHECK} DONE! [Forward this vote to a group]({link})"
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())

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

    def execute(self, bot, update, args):
        # We don't need this method since we already have a ConversationHandler
        pass
