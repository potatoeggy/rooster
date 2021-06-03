import json
import configparser
import os
import time
from selenium import webdriver
from selenium.common.exceptions import *

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
        self.read()
    
    def read(self):
        self.config.read(["config.ini", os.path.abspath(os.path.dirname(__file__)) + "config.ini"])
        general = self.config["rooster"]
        self.log_level = general.getint("LogLevel", fallback=1)
        self.admin_ids = list(map(int, general.get("AdminIds", fallback="").split(",")))
        self.headless = general.getboolean("Headless", fallback=True)
        self.dry_run = general.getboolean("DryRun", fallback=False)
        self.debug_guild = general.getint("DebugGuild", fallback=None)

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
        self.read()
    
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
    def __init__(self, log: Logger, config: Config):
        self.log = log
        self.config = config
        self.driver = None
        self.new_driver()
    
    def close(self):
        self.driver.quit()
    
    def new_driver(self):
        self.log.debug("Initialising web engine...")
        if self.driver is not None:
            self.driver.quit()
        
        options = webdriver.ChromeOptions()
        options.add_argument("no-sandbox")
        options.add_argument("disable-dev-shm-usage")
        if self.config.headless:
            options.add_argument("headless")
            options.add_argument("user-agent=\"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36\"")
        self.driver = webdriver.Chrome(options=options)

        self.driver.implicitly_wait(10)
        self.driver.set_page_load_timeout(15)
        self.log.info("Web engine initialised.")

        self.log.debug("Logging in to Google...")
        self.driver.get("https://google.yrdsb.ca")
        self.driver.find_element_by_id("UserName").send_keys(self.config.email.split("@")[0])
        self.driver.find_element_by_id("Password").send_keys(self.config.password)
        self.driver.find_element_by_id("LoginButton").click()

        time.sleep(1)
        if "speedbump" in self.driver.current_url:
            self.driver.find_element_by_xpath('//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div/div/button').click()
            self.log.debug("Speedbump passed.")

        time.sleep(1)
        if "drive.google.com" not in self.driver.current_url:
            self.log.error("Authentication failed.", abort=True)

        self.log.info("Google authentication successful.")
        
    def ping_meet(self, link) -> bool:
        if not "meet.google.com" in link:
            self.log.debug(f"{link} is not a Meet link, assume True")
            return True
        
        try:
            self.driver.get(link)
            time.sleep(2)
        except InvalidSessionIdException:
            self.log.warn("Invalid session ID, restarting driver...")
            self.new_driver()
            return False
        except TimeoutException:
            self.log.warn("Timed out while loading link, restarting driver...")
            time.sleep(10)
            self.new_driver()
            return False
        
        html = self.driver.page_source
        if "Join now" in html or "Ask to join" in html or "are in this call" in html:
            # meet is open
            return True
        return False
        