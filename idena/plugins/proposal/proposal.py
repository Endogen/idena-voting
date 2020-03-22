import idena.emoji as emo
import idena.utils as utl
import re

from enum import auto
from idena.plugin import IdenaPlugin
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ParseMode
from telegram.ext import CallbackQueryHandler, RegexHandler, CommandHandler, \
    ConversationHandler, MessageHandler, Filters


class Proposal(IdenaPlugin):

    TYPE = auto()
    CANCEL = auto()

    def __enter__(self):
        self.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler('proposal', self.choose)],
                states={
                    self.TYPE:
                        [RegexHandler("^(Vote)$", self.vote, pass_user_data=True),
                         RegexHandler("^(Proposal)$", self.proposal, pass_user_data=True)]
                },
                fallbacks=[CommandHandler('create', self.choose)],
                allow_reentry=True),
            group=1)

        return self

    def choose(self, bot, update):
        reply_msg = "Which type of vote do you want to create?"

        buttons = [
            KeyboardButton("Vote"),
            KeyboardButton("Proposal")
        ]

        cancel_btn = [KeyboardButton("Cancel")]

        menu = utl.build_menu(buttons, n_cols=2, footer_buttons=cancel_btn)
        reply_mrk = ReplyKeyboardMarkup(menu, resize_keyboard=True)
        update.message.reply_text(reply_msg, reply_markup=reply_mrk)

        return self.TYPE

    def vote(self, bot, update, user_data):
        update.message.reply_text("VOTE")
        return ConversationHandler.END

    def proposal(self, bot, update, user_data):
        update.message.reply_text("PROPOSAL")
        return ConversationHandler.END

    def execute(self, bot, update, args):
        # We don't need this method since we already have a ConversationHandler
        pass
