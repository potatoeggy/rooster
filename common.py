# helper module for i/o
import datetime
import os
import sys
import json
import time

import requests
from selenium import webdriver
from selenium.common.exceptions import *

# prints the help page and exits
def show_help():
	print(
"""
Usage:	python schoolschedule.py [options...]
  where options include:

General options
  --config <path>			Use configuration file at <path>.
  --verbose				Run with extended output (debug mode).
  --run-on-weekends			Do not exit when weekend is detected.
  --help, -h				Print this help screen.

Browser options
  --worker-visible			Run with the browser visible.
  --render-backend <driver>		Use <driver> as the browser backend (either "geckodriver" or "chromedriver").
  --driver-path <path>			Use <path> as the path to the driver executable.
  --driver-log <path>			Use <path> as the path to the driver log file.

Special options
  --use-class-order			Override the order of classes based on period.

Secrets options
  --gmail-address <address>		Use <address> as the Google account email address for Meet lookups.
  --yrdsb-password <password>		Use <password> as the password for authentication with YRDSB for Meet lookups.
  --discord-url <url>			Use <url> as the URL to send Discord webhooks to.
  --admin-user-id <id>			Use <id> as the Discord user ID to ping in case of emergencies.
""")

class Class:
	def __init__(self, jsondict):
		# jsondict must be dict with below vars as keys - period and enabled are int and boolean while the rest are strings
		self.name = jsondict["name"]
		self.teacher = jsondict["teacher"]
		self.period = jsondict["period"]
		self.discord_role = jsondict["role"]
		self.link = jsondict["link"]
		self.enabled = jsondict["enabled"]
	
	def get_discord_message(self):
		return f"<@&{self.discord_role}>, **{self.name}** with {self.teacher} is now **open** at <{self.link}>!"

class Period:
	def __init__(self, jsondict):
		# jsondict must be dict with "start_time" and "end_time" as keys with values of "HH:mm"
		self.start_time = datetime.datetime.combine(datetime.date.today(), datetime.time(*(map(int, jsondict["start_time"].split(":"))))) - datetime.timedelta(minutes=5)
		self.end_time = datetime.datetime.combine(datetime.date.today(), datetime.time(*(map(int, jsondict["end_time"].split(":")))))

class communicator:
	__slots__ = ["verbose", "period_data", "class_data", "gmail_address", "yrdsb_password", "webhook_url", "admin_user_id", "worker_visible", "render_backend", "driver_path", "driver_log", "run_on_weekends", "class_order", "override_days"]
	def __init__(self):
		self.verbose = True
		self.read_config()

	def now(self):
		return datetime.datetime.now()

	def read_config(self):
		self.debug("Reading configuration")
		config_file = os.path.join(sys.path[0], "config.json")
		try:
			config_file = sys.argv[sys.argv.index("--config") + 1]
		except ValueError:
			pass # user did not specify custom conf location
		except IndexError:
			show_help()
			exit()
		
		# load config from file
		with open(config_file, "r") as file:
			data = file.read()
		obj = json.loads(data)

		def check_config(key, fallback):
			# TODO: consider environment variables
			result = obj[key] if key in obj else fallback
			args_key = "--" + key.replace("_", "-")
			try:
				if type(fallback) is not bool:
					result = type(fallback)(sys.argv[sys.argv.index(args_key) + 1])
				elif args_key in sys.argv:
					result = True # only something like --verbose is needed instead of --verbose True
			except ValueError:
				pass # user did not specify conf in command line
			except IndexError:
				show_help() # user used option without providing value after
			return result
		
		# mandatory fields, we want to crash if these are not found
		self.gmail_address = obj["gmail_address"] # gapps account
		self.yrdsb_password = obj["yrdsb_password"] # password in plaintext :P
		self.webhook_url = obj["discord_url"] # discord webhook url
		self.admin_user_id = obj["admin_user_id"] # discord user id to ping in emergencies
		self.period_data = obj["period_data"]
		self.class_data = obj["class_data"]

		# optional fields
		self.verbose = check_config("verbose", False) # if debug statements are printed
		self.worker_visible = check_config("worker_visible", False) # if browser window is visible
		self.render_backend = check_config("render_backend", "chromedriver") # one of "chromedriver" or "geckodriver"
		self.driver_path = check_config(f"{self.render_backend}_path", f"/usr/bin/{self.render_backend}")
		self.driver_log = check_config(f"{self.render_backend}_log", f"{self.render_backend}.log")
		self.run_on_weekends = check_config("run_on_weekends", False)
		self.class_order = check_config("class_order", [])
		self.override_days = check_config("override_days", [])
		override_period_data = check_config("override_period_data", [])
	
		if (not self.run_on_weekends) and self.now().weekday() >= 5:
			self.debug("Current day is a weekend, exiting.", 1)
			exit()
		if "{date:%Y-%m-%d}".format(date=self.now()) in self.override_days:
			self.debug("Current day is in override_days, using override_period_data.")
			self.period_data = override_period_data
		
	def debug(self, string, priority: int = 0):
		prefixes = ["INFO", "WARN", "ERROR"]
		if self.verbose or priority > 0: # do not report debug statements
			print(f"{self.now()}: [{prefixes[priority]}]: {string}")
	
	def send_message(self, string, priority=0):
		if string != "":
			self.debug(string, priority)
		payload = { "content": string }
		try:
			requests.post(self.webhook_url, data=payload)
		except Exception:
			self.debug("Something borked when sending a message to Discord", 2)

	
	def send_help(self, string="", abort=True):
		self.send_message(f"<@!{self.admin_user_id}>, manual intervention required! {string}", priority=2)
		if abort:
			exit()


class driver:
	__slots__ = ["driver"]
	def __init__(self, com: communicator):
		com.debug("Initialising web engine...")
		# initialise web engine
		if com.render_backend == "geckodriver": # note firefox is borked in headless
			if not com.worker_visible:
				com.debug("Firefox currently does not support Google Meet in headless mode. Expect crashes.", 1)
			options = webdriver.firefox.options.Options()
			options.headless = not com.worker_visible
			profile = webdriver.FirefoxProfile()
			profile.DEFAULT_PREFERENCES["frozen"]["dom.webdriver.enabled"] = False
			self.driver = webdriver.Firefox(options=options, firefox_profile=profile, executable_path=com.driver_path, service_log_path=com.driver_log)
		elif com.render_backend == "chromedriver":
			options = webdriver.ChromeOptions()
			if not com.worker_visible:
				options.add_argument("headless")
				options.add_argument("user-agent=\"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36\"")
			self.driver = webdriver.Chrome(options=options, executable_path=com.driver_path, service_log_path=com.driver_log)
		else:
			com.debug(f"{com.render_backend} is not a valid render backend.", 2)
			exit()
		
		self.driver.implicitly_wait(10)

		com.debug("Logging into Google...")
		# login to google to use lookup links
		self.driver.get("https://accounts.google.com/ServiceLogin?continue=https://google.com")
		self.driver.implicitly_wait(10)
		self.driver.find_element_by_id("identifierId").send_keys(com.gmail_address) # input email
		self.driver.find_element_by_id("identifierNext").click()

		self.driver.find_element_by_id("UserName").send_keys(com.gmail_address.split("@")[0]) # YRDSB login field
		self.driver.find_element_by_id("Password").send_keys(com.yrdsb_password)
		self.driver.find_element_by_id("LoginButton").click()

		time.sleep(3) # google is slow

		if "speedbump" in self.driver.current_url:
			self.driver.find_element_by_xpath('//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div/div/button').click()
			com.debug("speedbump passed")
	
	def ping_meet(self, c: Class, com: communicator):
		if not "meet.google.com" in c.link: # assume zoom
			com.debug(f"Zoom detection not available for {c.name}, sending Discord hook at first opportunity")
			com.send_message(c.get_discord_message())
			return True
		try:
			self.driver.get(c.link)
			time.sleep(3)
		except InvalidSessionIdException:
			com.send_help("Invalid session ID, skipping classes, expect borks")
			return True
		
		html = self.driver.page_source
		if "Ready to join?" in html or "Ask to join" in html:
			# meet is open
			com.send_message(c.get_discord_message())
			return True
		elif "Not your computer?" in html:
			# not logged in even when bot is supposed to be logged in
			com.send_help("Bot is not logged in.")
			return True
		elif "Check your meeting code" in html or "You can't create a meeting yourself" in html or "meeting hasn't started" in html:
			# meet is not open, continue waiting
			pass
		elif "Your meeting code has expired" in html:
			# right after class or link needs to be updated, or class was dismissed early
			com.send_help(f"Link needs to be updated for {c.name}", abort=False)
			return True
		elif "Invalid video call name" in html:
			com.send_help(f"Invalid link for {c.name}", abort=False)
			return True
		elif "Getting ready" in html:
			com.send_help("Delay is too slow, Google is still getting ready")
		elif "You can't join this video call" in html:
			com.send_help(f"Google bot detection triggered or not authenticated with {c.name}")
			return True
		else:
			com.send_help(f"Something unexpected happened with {c.name}", abort=False)
		return False
		

def init_classes(com: communicator):
	com.debug("Processing class data...")
	classes = []

	# if no classes there is nothing to do
	if len(com.class_data) == 0:
		com.debug("Exiting because no classes found.", 2)
		exit()

	# change json to object
	for c in com.class_data:
		classes.append(Class(c))
	classes.sort(key=lambda c: c.period)

	if class_order is None:
		class_order = sorted(list(set([c.period for c in classes])))
	# takes sorted by period classes list and splits it into smaller lists of the same period 
	sorted_classes = [[] for i in class_order]
	for i, a in enumerate(class_order):
		for c in classes:
			if c.period == a:
				sorted_classes[i].append(c)

	com.debug(f"Found {len(classes)} class(es).")
	return sorted_classes

def init_periods(com: communicator):
	com.debug("Processing period data...")
	periods = []

	# if no periods there is nothing to do
	if len(com.period_data) == 0:
		com.debug("Exiting because no periods found.", 2)
		exit()
	
	# change json to object
	for p in com.period_data:
		periods.append(Period(p))

	sorted_periods = sorted(periods, key=lambda p: p.start_time)
	com.debug(f"Found {len(sorted_periods)} period(s).")
	return sorted_periods