from telegram import ParseMode
from idena.plugin import IdenaPlugin


class Start(IdenaPlugin):

    INTRO_FILE = "intro.md"

    @IdenaPlugin.threaded
    def execute(self, bot, update, args):
        if args:
            arg = args[0]

            # TODO: Read newly created poll / proposal and post it
            if arg == "poll":
                update.message.reply_text("SHOW NEWLY CRATED POLL")
            elif arg == "proposal":
                update.message.reply_text("SHOW NEWLY PROPOSAL POLL")
            return

        user = update.effective_user

        intro = self.get_resource(self.INTRO_FILE)
        intro = intro.replace("{{firstname}}", user.first_name)

        update.message.reply_text(intro, parse_mode=ParseMode.MARKDOWN)
