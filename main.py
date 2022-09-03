import asyncio
import json
import logging.config
import os.path
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram.request import HTTPXRequest


logging.config.fileConfig('logs/logging.ini', disable_existing_loggers=False)
log = logging.getLogger(__name__)


class Settings:
    __instances__ = dict()
    __locks__ = {'main': threading.RLock()}

    def __new__(cls, location: str):
        if not location.endswith('.json'):
            raise AttributeError('Settings can only use .json files')
        if not os.path.exists(location):
            raise FileNotFoundError(f'Settings({location}) failed: File does not exist')
        if (settings := cls.__instances__.get(location)) is None:
            settings = cls.__instances__[location] = super().__new__(cls)
            settings.__first_init__(location)
        return settings

    @property
    def lock(self):
        return self.__locks__[self.__location__]

    def __first_init__(self, location):
        self.__locks__[location] = threading.RLock()
        self.__run_init__ = True

    def __init__(self, location: str):
        if self.__run_init__:
            self.__location__ = location
            self.token = ''
            self.database = ''
            self.subscribers = dict()
            self.animal = ''
            self.description = ''
            self.channels = {'hourly': 0, 'log': 0, 'queue': 0}
            self.triggers = {'text': [], 'regex': [], 'sticker': []}
            self.bot_commands = {
                '!c': {'description': 'Request n number !animal images.', 'privilege': 'User'},
                '!c_info': {'description': 'Detailed information regarding what the bot uses to run.', 'privilege': 'User'},
                'subscribe': {'description': 'Menu for choosing your chats subscription to !animal.', 'privilege': 'Admin'}
            }
            self.telethon_keys = {'session': '', 'api_id': 0, 'api_hash': ''}
            self.twitter_keys = {'access_token_key': '', 'access_token_secret': '', 'consumer_key': '', 'consumer_secret': ''}
            self.load()
            self.__run_init__ = False

    def load(self):
        with self.lock:
            self.__dict__.update(**json.load(open(self.__location__, 'r')))

    def save(self):
        with self.lock:
            # noinspection PyTypeChecker
            json.dump(dict(filter(lambda key: not key[0].startswith('__'), self.__dict__.items())), open(self.__location__, 'w+'))


class HourlyBot:
    __locks__ = {'main': threading.RLock(), 'image-hash': threading.RLock()}
    __instances__ = dict()

    def __new__(cls, settings: Settings):
        if (bot := cls.__instances__.get(settings)) is None:
            bot = cls.__instances__[settings] = super().__new__(cls)
            bot.__first_init__(settings)
        return bot

    @property
    def lock(self):
        return self.__locks__[self.__location__]

    def __first_init__(self, settings: Settings):
        self.__locks__[settings.__location__] = threading.RLock()
        self.__location__ = settings.__location__
        self.settings = settings
        self.__run_init__ = True

    def __init__(self, settings: Settings):
        if self.__run_init__:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.app = ApplicationBuilder().token(settings.token).request(HTTPXRequest(40, connect_timeout=120)).build()
            self.commands()
            self.loop.run_until_complete(self.app.initialize())
            self.loop.run_until_complete(self.app.updater.initialize())
            self.loop.run_until_complete(self.app.updater.start_polling())
            self.loop.run_until_complete(self.app.start())
            threading.Thread(target=self.run_forever).start()

    def run_forever(self):
        try:
            self.loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as exc:
            self.app.updater.start_polling().close()
            raise exc
        finally:
            try:
                if self.app.updater.running:  # type: ignore[union-attr]
                    self.loop.run_until_complete(self.app.updater.stop())
                if self.app.running:
                    self.loop.run_until_complete(self.app.stop())
                self.loop.run_until_complete(self.app.shutdown())
            finally:
                self.loop.close()

    def commands(self):
        self.app.add_handlers([
                CommandHandler('start', self.start, block=False)
            ], 0)

    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please wait while I am being worked on.")


if __name__ == '__main__':
    HourlyBot(Settings('conf/test.json'))
    HourlyBot(Settings('conf/test2.json'))
    try:
        while True:
            ...
    finally:
        for instance in HourlyBot.__instances__.values():
            instance.loop.stop()
