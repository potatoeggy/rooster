#!/usr/bin/python
import datetime
import json
import os
import time
import common
import sys

import requests
from selenium import webdriver

# returns a datetime object now for convenience
def now():
	return datetime.datetime.now()

# prints to console and to log
# TODO: put this in object to remove global verbose dependency

if __name__ == "__main__":
	if "--help" in sys.argv or "-h" in sys.argv:
		common.show_help()
	com = common.communicator()
	classes = common.init_classes(com)
	periods = common.init_periods(com)
	driver = common.driver(com)

	earliest = periods[0].start_time
	latest = periods[-1].end_time
	found = [[not c.enabled for c in a] for a in classes]

	com.debug(f"Ready.")
	
	# only run during school hours
	if now() > latest:
		com.debug(f"Current time {now()} is after end of last period at {latest}.", 2)
		exit()
	if all(all(a) for a in found):
		com.debug(f"No classes are enabled.", 2)
		exit()
	if earliest > now():
		seconds_until_first_period = (earliest-now()).total_seconds()
		com.debug(f"Sleeping for {seconds_until_first_period} seconds until first period.")
		time.sleep(seconds_until_first_period)
	
	current_period = 0	
	while now() < latest:
		if all(found[current_period]):
			try:
				next_period_time = periods[current_period+1].start_time
				seconds_until_next_period = (next_period_time-now()).total_seconds()
				classes_skipped = len(found[current_period])-sum(found[current_period])
				com.debug(f"All classes found for current period. Sleeping for {seconds_until_next_period} seconds for next period at {next_period_time}")

				current_period += 1
				# TODO: use a better sleep that will not desync
				time.sleep(seconds_until_next_period)
			except ValueError:
				# expected if a class has been skipped
				pass
			except IndexError:
				# All classes found and this is last period, we can exit now
				break
		
		for i, c in enumerate(classes[current_period]):
			if found[current_period][i] or not c.enabled:
				continue
			elif periods[current_period].end_time <= now(): # link not found for too long
				com.debug("Skipped class {0} as it is past its end time".format(c.name))
				found[current_period][i] = True
			elif periods[current_period].start_time <= now(): # between end and start times
				found[current_period][i] = driver.ping_meet(c, com)
		
		time.sleep(5)

	com.debug("Exiting...")
	driver.driver.quit()