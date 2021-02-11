#!/usr/bin/python
from selenium import webdriver
from collections import namedtuple
import requests
import datetime
import time
import json
import sys

# TODO: get rid of global vars
GMAIL_ADDRESS, YRDSB_PASSWORD, DISCORD_URL, ADMIN_USER_ID, VERBOSE, WORKER_VISIBLE, HAMMER_MODE, HAMMER_DELAY, GECKODRIVER_PATH, GECKODRIVER_LOG, CHROMEDRIVER_PATH, CHROMEDRIVER_LOG, RENDER_BACKEND = (None for i in range(13))

def debug(string):
	if VERBOSE:
		print("DEBUG:", string)

# returns a datetime object now for convenience
def now():
	return datetime.datetime.now()

# searches for a value in a container and returns a fallback if not found
def in_container(key, fallback, container):
	return container[key] if key in container else fallback

# prints the help page and exits
def show_help():
	print(
"""
Discord-Meet Pinger - pings a role when a meeting opens
""")
	exit()
class Class:
	def __init__(self, name, teacher, start_time, end_time, discord_role, link, enabled):
		self.name = name
		self.teacher = teacher
		self.start_time = datetime.datetime.combine(datetime.date.today(), datetime.time(*(map(int, start_time.split(":"))))) - datetime.timedelta(minutes=5)
		self.end_time = datetime.datetime.combine(datetime.date.today(), datetime.time(*(map(int, end_time.split(":")))))
		self.discord_role = discord_role
		self.link = link
		self.enabled = enabled
	
	def send_discord_message(self):
		payload = {
			"content": "<@&{0}>, **{1}** with {2} is now **open** at <{3}> !".format(self.discord_role, self.name, self.teacher, self.link)
		}

		if VERBOSE:
			print(payload)
		else:
			requests.post(DISCORD_URL, data=payload)
	
def send_help(string="", abort=True):
	if string != "":
		print(string)
	payload = { "content": f"<@!{ADMIN_USER_ID}>, manual intervention required! " + string }
	requests.post(DISCORD_URL, data=payload)
	if abort:
		exit()

# load custom config
def load_config():
	# TODO: get rid of this asap
	global GMAIL_ADDRESS, YRDSB_PASSWORD, DISCORD_URL, ADMIN_USER_ID, VERBOSE, WORKER_VISIBLE, HAMMER_MODE, HAMMER_DELAY, GECKODRIVER_PATH, GECKODRIVER_LOG, CHROMEDRIVER_PATH, CHROMEDRIVER_LOG, RENDER_BACKEND
	def check_config(key, fallback):
		# TODO: check if environment variable is set and use that?
		result = in_container(key, fallback, obj) # config file has lowest priority
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
	
	CONFIG_FILE = "config.json"
	try:
		CONFIG_FILE = sys.argv[sys.argv.index("--config") + 1]
	except ValueError:
		pass # user did not specify custom conf location
	except IndexError:
		show_help()

	# load config from file
	with open(CONFIG_FILE, "r") as file:
		data = file.read()

	obj = json.loads(data)

	# TODO: move all non-necessary global fields to be local instead being passed around
	# mandatory fields
	GMAIL_ADDRESS = obj["gmail_address"] # gapps account
	YRDSB_PASSWORD = obj["yrdsb_password"] # password in plaintext :P
	DISCORD_URL = obj["discord_url"] # discord webhook url
	ADMIN_USER_ID = obj["admin_user_id"] # discord user id to ping in emergencies

	# optional fields
	VERBOSE = check_config("verbose", False) # if debug statements are printed
	WORKER_VISIBLE = check_config("worker_visible", False) # if browser window is visible
	HAMMER_MODE = check_config("hammer_mode", True) # if start time and end time should be ignored
	HAMMER_DELAY = check_config("hammer_delay", 20) # delay between pings in hammer mode
	GECKODRIVER_PATH = check_config("geckodriver_path", "/usr/bin/geckodriver")
	GECKODRIVER_LOG = check_config("geckodriver_log", "./geckodriver.log")
	CHROMEDRIVER_PATH = check_config("chromedriver_path", "/usr/bin/chromedriver")
	CHROMEDRIVER_LOG = check_config("chromedriver_log", "./chromedriver.log")
	RENDER_BACKEND = check_config("render_backend", "chromedriver") # one of "chromedriver" or "geckodriver"

	class_data = obj["class_data"]

	# if no classes there is nothing to do
	if len(class_data) == 0:
		send_help("Exiting because no classes found.")
	
	return class_data

def process_class_data(class_data):
	classes = []
	sorted_classes = []

	# change json to object
	if not HAMMER_MODE:
		for c in class_data:
			classes.append(Class(c["name"], c["teacher"], c["start_time"], c["end_time"], c["role"], c["link"], c["enabled"]))
		sorted_classes = sorted(classes, key=lambda c: c.start_time) # sort by time started
	else:
		for c in class_data:
			classes.append(Class(c["name"], c["teacher"], None, None, c["role"], c["link"], c["enabled"]))

		sorted_classes = classes # pass it over since no sorting needed while hammer
	return classes, sorted_classes

def init_driver():
	# initialise web engine
	if RENDER_BACKEND == "geckodriver": # note firefox is borked in headless
		options = webdriver.firefox.options.Options()
		options.headless = not WORKER_VISIBLE
		profile = webdriver.FirefoxProfile()
		profile.DEFAULT_PREFERENCES["frozen"]["dom.webdriver.enabled"] = False
		driver = webdriver.Firefox(options=options, firefox_profile=profile, executable_path=GECKODRIVER_PATH, service_log_path=GECKODRIVER_LOG)
	elif RENDER_BACKEND == "chromedriver":
		options = webdriver.ChromeOptions()
		if not WORKER_VISIBLE:
			options.add_argument("headless")
			options.add_argument("user-agent=\"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36\"")
		driver = webdriver.Chrome(options=options, executable_path=CHROMEDRIVER_PATH, service_log_path=CHROMEDRIVER_LOG)
	else:
		send_help(f"ERROR: {RENDER_BACKEND} is not a valid render backend.")

	# login to google to use lookup links
	driver.get("https://accounts.google.com/ServiceLogin?continue=https://google.com")
	driver.implicitly_wait(10)
	driver.find_element_by_id("identifierId").send_keys(GMAIL_ADDRESS) # input email
	driver.find_element_by_id("identifierNext").click()

	driver.find_element_by_id("UserName").send_keys(GMAIL_ADDRESS.split("@")[0]) # YRDSB login field
	driver.find_element_by_id("Password").send_keys(YRDSB_PASSWORD)
	driver.find_element_by_id("LoginButton").click()

	time.sleep(3) # google is slow

	if "speedbump" in driver.current_url:
		driver.find_element_by_xpath('//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div/div/button').click()
		debug("speedbump passed")
	return driver

def init():
	class_data = load_config()
	classes, sorted_classes = process_class_data(class_data)
	driver = init_driver()
	return classes, sorted_classes, driver

def ping_meet(c, driver):
	driver.get(c.link)
	html = driver.page_source
	if not "meet.google.com" in c.link:
		print("Zoom detection not available for {0}, sending Discord hook at first opportunity".format(c.name))
		c.send_discord_message()
		found[i] = True
	elif "Ready to join?" in html:
		# meet is open
		c.send_discord_message()
		debug("class {0} message sent".format(c.name))
		found[i] = True
	elif "Not your computer?" in html:
		# not logged in even when bot is supposed to be logged in
		send_help("ERROR: Bot is not logged in.")
	elif "Check your meeting code" in html or "You can't create a meeting yourself" in html:
		# meet is not open, continue waiting
		pass
	elif "Your meeting code has expired" in html:
		# right after class or link needs to be updated, or class was dismissed early
		send_help(f"WARNING: Link needs to be updated for {c.name}", abort=False)
	elif "Invalid video call name" in html:
		send_help(f"ERROR: Invalid link for {c.name}", abort=False)
	elif "Getting ready" in html:
		print("WARNING: Delay is too slow, Google is still getting ready")
	elif "You can't join this video call" in html:
		send_help(f"ERROR: Google bot detection triggered or not authenticated with {c.name}")
	else:
		send_help(f"ERROR: Something unexpected happened with {c.name}")

if __name__ == "__main__":
	if "--help" in sys.argv or "-h" in sys.argv:
		show_help()

	classes, sorted_classes, driver = init()
	driver.implicitly_wait(15)
	earliest = sorted_classes[0].start_time
	latest = sorted_classes[-1].end_time
	found = [c.enabled for c in sorted_classes]

	# only run while in school hours
	while now() < latest and not all(found):
		if not HAMMER_MODE: # use the times given for each class
			try:
				# sleep until five minutes before next class
				earliest_valid_class = sorted_classes[0]
				for i, c in enumerate(sorted_classes):
					if not found[i]:
						earliest_valid_class = c
						break
				debug("sleeping for {0} seconds".format((earliest_valid_class.start_time-now()).total_seconds()))
				time.sleep((earliest_valid_class.start_time-now()).total_seconds())
			except ValueError:
				# expected as part of regular loop (oversleep might happen but is rare)
				pass
		
		for i, c in enumerate(sorted_classes):
			if found[i] or not c.enabled: continue
			if HAMMER_MODE:
				ping_meet(c, driver)
			elif c.end_time <= now(): # link not found for too long
				debug("Skipped class {0} as it is past its end time".format(c.name))
				found[i] = True
				continue
			elif c.start_time > now(): # not start time yet, we can exit because the array should be sorted
				break
			elif c.start_time <= now(): # between end and start times
				ping_meet(c, driver)
		
		time.sleep(5 if not HAMMER_MODE else HAMMER_DELAY) # combined with the delay in processing and getting this should add up to about 10 s delay per ping
	driver.quit()
