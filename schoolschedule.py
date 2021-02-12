#!/usr/bin/python
import datetime
import json
import os
import sys
import time
from collections import namedtuple

import requests
from selenium import webdriver

# TODO: remove all globals
VERBOSE = True # true for now because some debug statements are called prior to VERBOSE being set

def debug(string, urgent=False):
	if urgent:
		print(string)
	elif VERBOSE:
		print("DEBUG:", string)

# returns a datetime object now for convenience
def now():
	return datetime.datetime.now()

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

Secrets options
  --gmail-address <address>		Use <address> as the Google account email address for Meet lookups.
  --yrdsb-password <password>		Use <password> as the password for authentication with YRDSB for Meet lookups.
  --discord-url <url>			Use <url> as the URL to send Discord webhooks to.
  --admin-user-id <id>			Use <id> as the Discord user ID to ping in case of emergencies.
""")
	exit()
class Class:
	def __init__(self, name, teacher, period, discord_role, link, enabled):
		self.name = name
		self.teacher = teacher
		self.period = period
		self.discord_role = discord_role
		self.link = link
		self.enabled = enabled
	
	def get_discord_message(self):
		return f"<@&{self.discord_role}>, **{self.name}** with {self.teacher} is now **open** at <{self.link}> !"

class Period:
	def __init__(self, start_time, end_time):
		self.start_time = datetime.datetime.combine(datetime.date.today(), datetime.time(*(map(int, start_time.split(":"))))) - datetime.timedelta(minutes=5)
		self.end_time = datetime.datetime.combine(datetime.date.today(), datetime.time(*(map(int, end_time.split(":")))))

class DiscordCommunicator:
	def __init__(self, discord_url, admin_user_id):
		self.discord_url = discord_url
		self.admin_user_id = admin_user_id

	def send_message(self, string):
		if string != "":
			debug(f"{now()}: {string}", urgent=True)
		payload = { "content": string }
		#requests.post(self.discord_url, data=payload)
		print(payload) # TODO: DEBUG
	
	def send_help(self, string="", abort=True):
		self.send_message(string)
		if abort:
			exit()

def process_class_data(class_data, discord, period_order):
	classes = []

	# if no classes there is nothing to do
	if len(class_data) == 0:
		discord.send_help("Exiting because no classes found.")

	# change json to object
	for c in class_data:
		classes.append(Class(c["name"], c["teacher"], c["period"], c["role"], c["link"], c["enabled"])) # TODO: refactor to just plug in the whole dict to the constructor
	classes.sort(key=lambda c: c.period)

	if period_order is None:
		period_order = list(dict.fromkeys([c.period for c in classes])) # TODO: add python 3.6+ as dependency for ordered dict
	# takes sorted by period classes list and splits it into smaller lists of the same period 
	# TODO: get rid of the below bullshit
	sorted_classes = [[c for c in classes[[x.period for x in classes].index(i) : None if i == period_order[-1] else [x.period for x in classes].index(period_order[k+1])]] for k, i in enumerate(period_order)] # designed to be the most spaghetti out of all the spaghetti code i've made
	for i in sorted_classes:
		for j in i:
			print(j.period, sep=", ")

	debug(f"Found {len(classes)} class(es).")
	return sorted_classes

def process_period_data(period_data, discord):
	periods = []

	# if no periods there is nothing to do
	if len(period_data) == 0:
		discord.send_help("Exiting because no periods found.")
	
	# change json to object
	for p in period_data:
		periods.append(Period(p["start_time"], p["end_time"]))

	sorted_periods = sorted(periods, key=lambda p: p.start_time)
	debug(f"Found {len(sorted_periods)} period(s).")
	return sorted_periods

def init_driver(render_backend, worker_visible, driver_path, driver_log, discord):
	# initialise web engine
	if render_backend == "geckodriver": # note firefox is borked in headless
		if not worker_visible:
			debug("Firefox currently does not support Google Meet in headless mode. Expect crashes.", urgent=True)
		options = webdriver.firefox.options.Options()
		options.headless = not worker_visible
		profile = webdriver.FirefoxProfile()
		profile.DEFAULT_PREFERENCES["frozen"]["dom.webdriver.enabled"] = False
		driver = webdriver.Firefox(options=options, firefox_profile=profile, executable_path=driver_path, service_log_path=driver_log)
	elif render_backend == "chromedriver":
		options = webdriver.ChromeOptions()
		if not worker_visible:
			options.add_argument("headless")
			options.add_argument("user-agent=\"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36\"")
		driver = webdriver.Chrome(options=options, executable_path=driver_path, service_log_path=driver_log)
	else:
		discord.send_help(f"ERROR: {render_backend} is not a valid render backend.")
	return driver

def login_google(gmail_address, yrdsb_password, driver):
	# login to google to use lookup links
	driver.get("https://accounts.google.com/ServiceLogin?continue=https://google.com")
	driver.implicitly_wait(10)
	driver.find_element_by_id("identifierId").send_keys(gmail_address) # input email
	driver.find_element_by_id("identifierNext").click()

	driver.find_element_by_id("UserName").send_keys(gmail_address.split("@")[0]) # YRDSB login field
	driver.find_element_by_id("Password").send_keys(yrdsb_password)
	driver.find_element_by_id("LoginButton").click()

	time.sleep(3) # google is slow

	if "speedbump" in driver.current_url:
		driver.find_element_by_xpath('//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div/div/button').click()
		debug("speedbump passed")

def init():
	global VERBOSE
	# check command line arguments, config file, fallback
	def check_config(key, fallback):
		# TODO: consider environment variables
		result = obj[key] if key in obj else fallback
		args_key = "--" + key.replace("_", "-")
		try:
			if type(fallback) is not bool:
				result = type(fallback)(sys.argv[sys.argv.index(args_key) + 1])
			else:
				result = args_key in sys.argv # only something like --verbose is needed instead of --verbose True
		except ValueError:
			pass # user did not specify conf in command line
		except IndexError:
			show_help()
		return result
	
	# read from config file
	debug("Reading configuration...", urgent=True)
	config_file = os.path.join(sys.path[0], "config.json")
	try:
		config_file = sys.argv[sys.argv.index("--config") + 1]
	except ValueError:
		pass # user did not specify custom conf location
	except IndexError:
		show_help()

	# load config from file
	with open(config_file, "r") as file:
		data = file.read()
	obj = json.loads(data)

	# mandatory fields
	gmail_address = obj["gmail_address"] # gapps account
	yrdsb_password = obj["yrdsb_password"] # password in plaintext :P
	discord_url = obj["discord_url"] # discord webhook url
	admin_user_id = obj["admin_user_id"] # discord user id to ping in emergencies
	period_data = obj["period_data"] # TODO: call it class_order since that makes more sense
	class_data = obj["class_data"]

	# optional fields
	VERBOSE = check_config("verbose", False) # if debug statements are printed
	worker_visible = check_config("worker_visible", False) # if browser window is visible
	# TODO: consider removing two paths/logs since you can only use one anyway
	render_backend = check_config("render_backend", "chromedriver") # one of "chromedriver" or "geckodriver"
	driver_path = check_config(f"{render_backend}_path", f"/usr/bin/{render_backend}")
	driver_log = check_config(f"{render_backend}_log", f"{render_backend}.log")
	run_on_weekends = check_config("run_on_weekends", False)
	use_period_order = check_config("use_period_order", False)
	period_order = check_config("period_order", [])

	if VERBOSE:
		debug("Running in debug/verbose mode.")
	if (not run_on_weekends) and now().weekday() >= 5:
		debug("Current day is a weekend, exiting.", urgent=True)

	discord = DiscordCommunicator(discord_url, admin_user_id)
	debug("Processing class data...")
	sorted_classes = process_class_data(class_data, discord, period_order if use_period_order else None)
	debug("Processing period data...")
	sorted_periods = process_period_data(period_data, discord)
	debug("Initialising browser...")
	driver = init_driver(render_backend, worker_visible, driver_path, driver_log, discord)
	debug("Authenticating with Google...")
	login_google(gmail_address, yrdsb_password, driver)
	debug("Initialisation complete.")
	return (sorted_classes, sorted_periods, driver, discord)

def ping_meet(c, driver, discord):
	driver.get(c.link)
	html = driver.page_source
	if not "meet.google.com" in c.link:
		debug(f"Zoom detection not available for {c.name}, sending Discord hook at first opportunity")
		discord.send_message(c.get_discord_message())
		found[i] = True
	elif "Ready to join?" in html:
		# meet is open
		discord.send_message(c.get_discord_message())
		debug(f"Class {c.name} message sent")
		found[i] = True
	elif "Not your computer?" in html:
		# not logged in even when bot is supposed to be logged in
		discord.send_help("ERROR: Bot is not logged in.")
	elif "Check your meeting code" in html or "You can't create a meeting yourself" in html:
		# meet is not open, continue waiting
		pass
	elif "Your meeting code has expired" in html:
		# right after class or link needs to be updated, or class was dismissed early
		discord.send_help(f"WARNING: Link needs to be updated for {c.name}", abort=False)
	elif "Invalid video call name" in html:
		discord.send_help(f"ERROR: Invalid link for {c.name}", abort=False)
	elif "Getting ready" in html:
		print("WARNING: Delay is too slow, Google is still getting ready")
	elif "You can't join this video call" in html:
		discord.send_help(f"ERROR: Google bot detection triggered or not authenticated with {c.name}")
	else:
		discord.send_help(f"ERROR: Something unexpected happened with {c.name}", abort=False)

# main event
if __name__ == "__main__":
	if "--help" in sys.argv or "-h" in sys.argv:
		show_help()

	sorted_classes, sorted_periods, driver, discord = init()
	driver.implicitly_wait(15)
	earliest = sorted_periods[0].start_time
	latest = sorted_periods[-1].end_time
	found = [[not c.enabled for c in a] for a in sorted_classes]

	debug(f"Ready.", urgent=True)

	# only run while in school hours
	if now() > latest:
		debug(f"Current time {now()} is after end of last period at {latest}.", urgent=True)
	if all(found):
		debug(f"No classes are enabled.", urgent=True)
	if earliest > now():
		seconds_until_first_period = (earliest-now()).total_seconds()
		debug(f"Sleeping for {seconds_until_first_period} seconds until first period.")
		time.sleep(seconds_until_first_period)
	
	current_period = 0
	while now() < latest:
		if all(found[current_period]):
			try:
				next_period_time = sorted_periods[current_period+1].start_time
				seconds_until_next_period = (next_period_time-now()).total_seconds()
				classes_skipped = len(found[current_period])-sum(found[current_period])
				debug(f"All classes found for current period. Sleeping for {seconds_until_next_period} seconds for next period at {next_period_time}")

				current_period += 1
				time.sleep(seconds_until_next_period)
			except ValueError:
				# expected if a class has been skipped
				pass
			except IndexError:
				# All classes found and this is last period, we can exit now
				break
		
		for i, c in enumerate(sorted_classes[current_period]):
			if found[current_period][i] or not c.enabled:
				continue
			elif sorted_periods[current_period].end_time <= now(): # link not found for too long
				debug("Skipped class {0} as it is past its end time".format(c.name))
				found[current_period][i] = True
			elif sorted_periods[current_period].start_time <= now(): # between end and start times
				ping_meet(c, driver, discord)
		
		time.sleep(10) # combined with the delay in processing and getting this should add up to about 10 s delay per ping
	debug("Exiting...")
	driver.quit()
