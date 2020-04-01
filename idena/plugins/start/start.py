import logging
import idena.utils as utl

from collections import OrderedDict
from idena.plugin import IdenaPlugin
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler


class Start(IdenaPlugin):

    INTRO_FILE = "intro.md"
    CMD_PROP = "proposal"
    CMD_VOTE = "vote"

    def __enter__(self):
        self.add_handler(CallbackQueryHandler(self._callback), group=1)
        return self

    @IdenaPlugin.threaded
    def execute(self, bot, update, args):
        if args:
            arg_list = args[0].split("_")
            cmd = arg_list[0]
            uid = arg_list[1]

            if cmd == self.CMD_VOTE:
                sql = self.get_global_resource("select_vote.sql")
                res = self.execute_global_sql(sql, uid)

                if not res["success"]:
                    error = f"Not possible to post vote: {res['data']}"
                    logging.error(error)
                    self.notify(error)
                    return

                url = self.config.get("explorer_url")

                question = res["data"][0][2]
                end = res["data"][0][7]

                # TODO: How to link that to a tutorial?
                howto = "Send small amount of DNA to one of the addresses to vote for associated option."

                counter = 0
                options = str()
                for op in res["data"]:
                    counter += 1
                    address = op[4]
                    option = op[3]

                    short_addr = f"{address[:12]}...{address[-12:]}"
                    options += f"\n\n{counter}) {option}\n[{short_addr}]({url}{address})"

                vote = self.get_resource("vote.md")
                vote = vote.replace("{{question}}", question)
                vote = vote.replace("{{options}}", options)
                vote = vote.replace("{{howto}}", howto)
                vote = vote.replace("{{end}}", end)

                update.message.reply_text(
                    vote,
                    reply_markup=self._result_button(cmd, uid),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                    quote=False)

            elif cmd == "proposal":
                # TODO: Implement
                pass

            return

        user = update.effective_user

        intro = self.get_resource(self.INTRO_FILE)
        intro = intro.replace("{{firstname}}", user.first_name)

        update.message.reply_text(intro, parse_mode=ParseMode.MARKDOWN)

    def _result_button(self, cmd, uid):
        menu = utl.build_menu([InlineKeyboardButton("Show Results", callback_data=f"{cmd}_{uid}")])
        return InlineKeyboardMarkup(menu, resize_keyboard=True)

    # TODO: Add timeframe for allowed update
    def _callback(self, bot, update):
        query = update.callback_query

        data = query.data.split("_")
        command = data[0]
        vote_id = data[1]

        if command == self.CMD_VOTE:
            sql = self.get_global_resource("select_vote.sql")
            res = self.execute_global_sql(sql, vote_id)

            if not res["success"]:
                error = f"Not possible to retrieve vote data: {res['data']}"
                logging.error(error)
                self.notify(error)
                return

            topic = None
            vote_data = dict()
            for op in res["data"]:
                topic = op[2]

                for key, value in self.api.valid_trx_for(op[4]).items():
                    if key in vote_data:
                        if value["timestamp"] < vote_data[key]["timestamp"]:
                            continue

                    vote_data[key] = value

            all = {
                "topic": topic,
                "total_votes": None,
                "options": OrderedDict()
            }

            total_votes = 0
            for key, value in vote_data.items():
                total_votes += 1

                if value["option"] in all["options"]:
                    all["options"][value["option"]] = all["options"][value["option"]].append(key)
                else:
                    all["options"][value["option"]] = [key]

            all["total_votes"] = total_votes

            counter = 0
            result = str()
            for op, votes in all["options"].items():
                counter += 1
                count = len(votes)

                # TODO: Could be that an option is not in here if nobody sent something...
                percent = 0 if count == 0 else (count / all["total_votes"] * 100)
                done = '█' * int(percent / 6.666)
                progress = f"{done}"

                if str(percent).endswith(".0"):
                    percent = str(percent)[:-2]
                if "." in str(percent):
                    percent = f"{percent:.2f}"

                result += f"\n{counter}) {progress}\n{percent}% (Votes: {count})"

            result = f"{result}\n\nTotal Votes: {all['total_votes']}"

            bot.answer_callback_query(query.id, result, show_alert=True)

        elif command == self.CMD_PROP:
            # TODO: Implement
            pass

        else:
            bot.answer_callback_query(query.id, str())
