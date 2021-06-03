import json
import configparser
import os

class Logger:
    LOG_STRINGS = ["DEBUG", " INFO", " WARN", "ERROR"]
    DEBUG_LEVEL = 0
    INFO_LEVEL = 1
    WARN_LEVEL = 2
    ERROR_LEVEL = 3

    def __init__(self, log_level: int = 0):
        self.log_level = log_level

    def _log(self, msg, log_level: int):
        if log_level >= self.log_level:
            print(f"{Logger.LOG_STRINGS[log_level]}: {msg}")

    def debug(self, msg):
        self._log(msg, Logger.DEBUG_LEVEL)

    def info(self, msg):
        self._log(msg, Logger.INFO_LEVEL)

    def warn(self, msg):
        self._log(msg, Logger.WARN_LEVEL)

    def error(self, msg, abort: bool = False):
        self._log(msg, Logger.ERROR_LEVEL)
        if abort:
            exit(1)

    def set_log_level(self, log_level: int):
        self.log_level = log_level


class Config:
    def __init__(self, log: Logger):
        self.log = log
        self.config = configparser.ConfigParser()
    
    def read(self):
        self.config.read(os.path.abspath(os.path.dirname(__file__)) + "config.ini")
        general = self.config["rooster"]
        self.log_level = general.getint("LogLevel", fallback=1)
        self.admin_ids = list(map(int, general.get("AdminIds", fallback="").split(",")))
        self.headless = general.getboolean("Headless", fallback=True)
        self.dry_run = general.getboolean("DryRun", fallback=False)

        secrets = self.config["secrets"]
        self.email = secrets.get("Email")
        self.password = secrets.get("Password")
        self.token = secrets.get("BotToken")

        if self.email is None or self.password is None or self.token is None:
            self.log.error("Missing secrets. Please check your configuration.", abort=True)

class Data:
    def __init__(self, log: Logger):
        self.data = {}
        self.log = log
    
    def read(self):
        try:
            with open("data.json", "r") as file:
                self.data = json.load(file)
        except FileNotFoundError:
            # expected, likely first run
            pass
    
    def write(self):
        with open("data.json", "w") as file:
            json.dump(self.data, file, indent=4)

class Driver:
    pass