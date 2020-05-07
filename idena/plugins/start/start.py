import logging
import idena.utils as utl

from collections import OrderedDict
from datetime import datetime
from idena.plugin import IdenaPlugin
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler


class Start(IdenaPlugin):

    INTRO_FILE = "intro.md"
    CMD_VOTE = "vote"

    def __enter__(self):
        self.add_handler(CallbackQueryHandler(self._callback), group=1)
        return self

    @IdenaPlugin.threaded
    def execute(self, bot, update, args):
        if args:
            uid = args[0]

            sql = self.get_global_resource("select_vote.sql")
            res = self.execute_global_sql(sql, uid)

            if not res["success"]:
                error = f"Not possible to post vote: {res['data']}"
                logging.error(error)
                self.notify(error)
                return

            url = self.config.get("explorer_url")

            question = res["data"][0][2]
            end = "[NO END-DATE]" if not res["data"][0][7] else res["data"][0][7]
            howto = "Send small amount of DNA to one of the addresses to vote for associated option."

            counter = 0
            options = str()
            for op in res["data"]:
                counter += 1
                address = op[4]
                option = op[3]

                options += f"\n\n{counter}) {option}\n[{address}]({url}{address})"

            vote = self.get_resource("vote.md")
            vote = vote.replace("{{question}}", question)
            vote = vote.replace("{{options}}", options)
            vote = vote.replace("{{howto}}", howto)
            vote = vote.replace("{{end}}", end)

            logging.info(f"Vote created: {vote}")

            update.message.reply_text(
                vote,
                reply_markup=self._result_button(uid),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                quote=False)

            return

        user = update.effective_user

        intro = self.get_resource(self.INTRO_FILE)
        intro = intro.replace("{{firstname}}", user.first_name)

        update.message.reply_text(intro, parse_mode=ParseMode.MARKDOWN)

    def _result_button(self, uid):
        menu = utl.build_menu([InlineKeyboardButton("Show Results", callback_data=f"{uid}")])
        return InlineKeyboardMarkup(menu, resize_keyboard=True)

    def _callback(self, bot, update):
        query = update.callback_query
        vote_id = query.data

        sql = self.get_global_resource("select_vote.sql")
        res = self.execute_global_sql(sql, vote_id)

        if not res["success"]:
            error = f"Not possible to retrieve vote data: {res['data']}"
            logging.error(error)
            self.notify(error)
            return

        logging.info(f"Raw: {res['data']}")

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

        option_nr = 0
        msg = str()
        for op, votes in result["options"].items():
            option_nr += 1
            nr_of_votes = len(votes)

            percent = 0 if nr_of_votes == 0 else (nr_of_votes / result["total_votes"] * 100)
            done = '█' * int(percent / 6.666)
            progress = f"{done}"

            if str(percent).endswith(".0"):
                percent = str(percent)[:-2]
            if "." in str(percent):
                percent = f"{percent:.2f}"

            msg += f"\n{option_nr}) {progress}\n{percent}% (Votes: {nr_of_votes})"

        msg = f"{msg}\n\nTotal Votes: {result['total_votes']}"

        bot.answer_callback_query(query.id, msg, show_alert=True)
