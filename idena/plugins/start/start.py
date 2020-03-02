from telegram import ParseMode
from idena.plugin import IdenaPlugin


class Start(IdenaPlugin):

    INTRO_FILE = "intro.md"

    @IdenaPlugin.threaded
    def execute(self, bot, update, args):
        if args:
            arg_list = args[0].split("_")
            cmd = arg_list[0]
            uid = arg_list[1]

            if cmd == "vote":
                # TODO: Create join on options
                sql = self.get_resource("select_vote.sql")
                res = self.execute_sql(sql, uid, plugin=cmd)
                update.message.reply_text(res)
            elif cmd == "proposal":
                update.message.reply_text("SHOW PROPOSAL")
            return

        user = update.effective_user

        intro = self.get_resource(self.INTRO_FILE)
        intro = intro.replace("{{firstname}}", user.first_name)

        update.message.reply_text(intro, parse_mode=ParseMode.MARKDOWN)
