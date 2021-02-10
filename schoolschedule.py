#!/usr/bin/python

from selenium import webdriver
import requests
import datetime
import time
import json

# TODO: ping users support
# TODO: cohort rotation system support — preprocessing?

# load config from file
with open("config.json", "r") as file:
	data = file.read()

obj = json.loads(data)
GMAIL_ADDRESS = obj["GMAIL_ADDRESS"]
YRDSB_PASSWORD = obj["YRDSB_PASSWORD"]
WORKER_VISIBLE = obj["WORKER_VISIBLE"]
GECKODRIVER_PATH = obj["GECKODRIVER_PATH"]
GECKODRIVER_LOG = obj["GECKODRIVER_LOG"]
CHROMEDRIVER_PATH = obj["CHROMEDRIVER_PATH"]
CHROMEDRIVER_LOG = obj["CHROMEDRIVER_LOG"]
RENDER_BACKEND = obj["RENDER_BACKEND"]
DISCORD_URL = obj["DISCORD_URL"]
CLASS_DATA = obj["CLASS_DATA"]

# if no classes there is nothing to do
if len(CLASS_DATA) == 0:
	print("Exiting because no classes found.")
	exit()

class Class:
	def __init__(self, name, teacher, start_time, end_time, link):
		self.name = name
		self.teacher = teacher
		self.start_time = datetime.datetime.combine(datetime.date.today(), datetime.time(*(map(int, start_time.split(":"))))) - datetime.timedelta(minutes=5)
		self.end_time = datetime.datetime.combine(datetime.date.today(), datetime.time(*(map(int, end_time.split(":")))))
		self.link = link
	
	def send_discord_message(self, DISCORD_URL):
		payload = {
			"content": "**{0}** with {1} is now **open** at {2}.".format(self.name, self.teacher, self.link)
		}
		requests.post(DISCORD_URL, data=payload)

classes = []

# change json to object
for c in CLASS_DATA:
	classes.append(Class(c["name"], c["teacher"], c["start_time"], c["end_time"], c["link"]))
sorted_classes = sorted(classes, key=lambda c: c.start_time) # sort by time started

# initialise web engine
if RENDER_BACKEND == "geckodriver":
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
	print("ERROR: No render backend found")
	exit()

# login to google to use lookup links
driver.get("https://accounts.google.com/ServiceLogin?continue=https://google.com")
driver.implicitly_wait(10)
driver.find_element_by_id("identifierId").send_keys(GMAIL_ADDRESS) # input email
driver.find_element_by_id("identifierNext").click()

driver.find_element_by_id("UserName").send_keys(GMAIL_ADDRESS.split("@")[0]) # YRDSB login field
driver.find_element_by_id("Password").send_keys(YRDSB_PASSWORD)
driver.find_element_by_id("LoginButton").click()

# set up waiting vars
driver.implicitly_wait(15)
earliest = sorted_classes[0].start_time
latest = sorted_classes[-1].end_time
def now():
	return datetime.datetime.now()

# only run while in school hours
while now() < latest and len(sorted_classes) > 0:
	try:
		# sleep until five minutes before next class
		print("DEBUG: sleeping for {0} seconds".format((sorted_classes[0].start_time-now()).total_seconds()))
		time.sleep((sorted_classes[0].start_time-now()).total_seconds())
	except ValueError:
		# it is past the time (negative) and some things might be wrong
		print("WARNING: Overslept, may have skipped class")
	
	for c in sorted_classes:
		if c.end_time <= now(): # link not found for too long
			print("WARNING: Skipped class {0} as it is past its end time".format(c.name))
			sorted_classes.remove(c)
			continue
		elif c.start_time > now(): # not start time yet, we can exit because the array should be sorted
			print(c.start_time, now())
			break
		elif c.start_time <= now(): # between end and start times
			driver.get(c.link)
			html = driver.page_source
			if "Ready to join?" in html:
				# meet is open
				c.send_discord_message(DISCORD_URL)
				classes.remove(c)
			elif "Not your computer?" in html:
				# not logged in even when bot is supposed to be logged in
				print("ERROR: Bot is not logged in.")
			elif "Check your meeting code" in html:
				# meet is not open, continue waiting
				pass
			elif "Your meeting code has expired" in html:
				# right after class or link needs to be updated, or class was dismissed early
				print("WARNING: Class dismissed early or link needs to be updated for", c.name)
				classes.remove(c)
			elif "Invalid video call name" in html:
				print("ERROR: Invalid link for", c.name)
				classes.remove(c)
			elif "Getting ready" in html:
				print("WARNING: Delay is too slow, Google is still getting ready")
			elif "You can't join this video call" in html:
				print("ERROR: Google bot detection triggered with", c.name)
			else:
				print("ERROR: Something is seriously broken with", c.name)
				classes.remove(c)
	
	time.sleep(5) # combined with the delay in processing and getting this should add up to about 20-30 s delay per ping
driver.quit()
