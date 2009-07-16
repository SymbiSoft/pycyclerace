# -*- coding: utf-8 -*-


__doc__ = """
Graphical python script to talk to a GPS, and display all sorts
 of useful information from it. Can talk to a NMEA Bluetooth GPS,
 or an internal GPS on a 5th Edition Phone.

 Also allows you to log your journeys to a simple  csv file.

Optionally also logs the GSM location to the file used by stumblestore,
 which you can later uplaod with stumblestore to http://gsmloc.org/
Can take photos which have the exif GPS tags, which indicate where and
 when they were taken.
 Both is not tested.

In future, the OS co-ords stuff should be made more general, to handle
 other countries
In future, some of the messages out to be translated into other languages

For now, on the main screen, hit * to increase logging frequency, # to
 decrease it, 0 to immediately log a point, and 8 to toggle logging
 on and off. Use 5 to toggle stumblestore GSM logging on and off. Use
 2 to switch between metric and imperial speeds (mph vs kmph)
On the Direction Of screen, use 1 and 3 to move between waypoints, 5
 to add a waypoint for the current location, and 8 to delete the
 current waypoint.
On the photos screen, use 1 and 3 to cycle between the possible
 resolutions, and enter or 0 to take a photo.

GPL
  Contributions from Cashman Andrus and Christopher Schmit

Nick Burch - v0.28 (04/05/2008)
"""
# Core imports - special ones occur later
import appuifw
import e32
import e32db
import math
import time
import os
import sysinfo
import thread
import audio # text to speech
import key_codes

from location import gsm_location
from graphics import *

######################### settings ##########################################

# All of our preferences live in a dictionary called 'pref'
pref = {} 			# general settings
userpref = {} 		# settings free to change by the users
log_track = None 	# log_file for racking the user's way
audio_info_on = True# if the speaker is eanbled
waypoints_xy = None	# saves the current track as (x,y) coords
track_xy = None		# saves the locations the users has passed
origin = [0,0]

def write_settings(set):
	global userpref

	filename = userpref['base_dir'] + 'settings.ini'
	file = open(filename, "w")
	keys = set.keys()
	keys.sort()
	for k in keys:
		file.write("%s=%s\n" % (k, set[k]))

def load_settings(set):
	global userpref
	filename = userpref['base_dir'] + 'settings.ini'
	try:
		file = open(filename, "r")
	except: return
	lines = file.readlines()

	for line in lines:
		l = line.strip()
		if len(l) == 0 or l[0] == '#' : continue

		parts = l.split('=')
		if len(parts) == 2 and len(parts[0]) > 0:
			set[parts[0]] = parts[1]
	file.close()


def set_value(dict, key, value, type = None):
	"""Set a (key, value) pair in a dictionary, if the key is not present,
		If the key is present, nothing happens, except a specific type
		is given, then it tries to convert the value to that type.
	"""
	if not dict.has_key(key):
		dict[key] = value

	# here the key definitely exists
	if type == 'bool':
		if dict[key] == "False":
			dict[key] = False
		elif dict[key] == "True":
			dict[key] = True
		# attention: never ever immplement an else case here, because
		# this would destroy the standard setting
	elif type == 'int':
		try: dict[key] = int(dict[key])
		except:
			print "Cannot convert %s to %s" % (key, type)
			sys.exit(-1)
	elif type == 'float':
		try: dict[key] = float(dict[key])
		except:
			print "Cannot convert %s to %s" % (key, type)
			sys.exit(-1)
	return

def initialize_settings():
	"""Initializes all key, value pairs with standards if they are not
	present. Every new seeting has to be registered in this function."""
	global pref
	global userpref

	set_value(userpref, 'disk','e:')
	# Do we have an E: disk (memory card?)
	## if c: is not a system drive, than better use c
	if not os.path.exists('c:\\System'):
		userpref['disk'] = 'c:'

	# Where we store our data and settings
	set_value(userpref, 'base_dir',userpref['disk'] + '\\Apps\\NMEA_Info\\')

	# Default bluetooth address to connect to
	# If blank, will prompt you to pick one
	set_value(pref,'def_gps_addr','')

	# By default, LocationRequestor will be used if found, otherwise
	#  bluetooth will be used. This may be used to force bluetooth
	#  even when LocationRequestor is found
	set_value(pref,'force_bluetooth',  False, 'bool')

	# Should we start off with metric or imperial speeds?
	# (Switch by pressing 2 on the main screen)
	set_value(userpref,'imperial_speeds', False, 'bool')

	# How many GGA sentences between logging
	# Set to 0 to prevent logging
	set_value(userpref,'log_interval', 0, 'int')
	set_value(userpref,'log_simple', True, 'bool')

	# File to log debug info into
	#set_value(pref,'debug_log_file', userpref['base_dir']  +'nmea_info_debug.log')


	# DB file to hold waypoints for direction-of stuff
	set_value(pref,'waypoints_db',userpref['base_dir'] + 'waypoints.db')


	# Should we also log GSM+lat+long in the stumblestore log file?
	# See http://gsmloc.org/ for more details
	set_value(pref,'gsmloc_logging', 0, 'int')


	# We want icons etc
	# Set this to 'large' if you want the whole screen used
	set_value(pref,'app_screen', 'normal')	#
	#pref['app_screen'] = 'large'	# softkeys visible
	#pref['app_screen'] = 'full'		# would be full screen
	# Define title etc
	set_value(pref,'app_title', "PyCycle Race")

	# Default location for "direction of"
	set_value(pref,'direction_of_lat', '52.520727')
	set_value(pref,'direction_of_long', '13.409586')
	set_value(pref,'direction_of_name', '(Berlin Alexanderplatz)')

	# seconds between two speech infos
	set_value(userpref,'audio_info_on', True, 'bool')		# text to speech messages activted ?
	set_value(userpref,'audio_info_interval', 120, 'int')	# in seconds
	set_value(userpref,'audio_alert_interval', 20, 'int')	# in seconds (urgent direction warnings)
	set_value(userpref,'minimum_warning_distance', 40.,'float')	# distance between two points before new warnings in meters
	set_value(pref,'maximum_warning_count', 2, 'int')	# how often shall a warning be given
	set_value(userpref,'minimum_speed_mps', 1., 'float')	# mps = meters per second
	# comment : maximum speeds observed while not moving
	# where approx. 12km/h = 3.3 m/s

	set_value(userpref,'min_direction_difference',10., 'float')  # min. 10 degrees denote a turning point, values below are irgnored, while searching the next turning point

	set_value(pref,'use_db', False, 'bool') # save track in db

	return

save_form = False

def settings_form_save(save_now):
	global settings_form
	global userpref
	global save_form

	save_form = save_now
	return save_form

class SettingsForm:
	def show(self, pref):
		global save_form
		global audio_info_on
		keys = pref.keys()
		keys.sort()
		fields = []
		for k in keys:
			uk = unicode(k)
			if type(pref[k]) == type(0) or type(pref[k]) == type(100L) : # check if int or long
				fields.append( (uk, 'number', pref[k]) )
			elif type(pref[k]) == type(1.2):
				fields.append( (uk, 'float', pref[k]) )
			elif type(pref[k]) == type(True) : # check if int
				selection = 1
				if pref[k] : selection = 0
				fields.append( (unicode(k), 'combo', ( [u"True", u"False"],selection)))
			elif type(pref[k]) == type('string') : # check if int
				fields.append( (uk, 'text', unicode(pref[k])) )
		self.form = appuifw.Form(fields,appuifw.FFormEditModeOnly)
		self.form.flags = appuifw.FFormEditModeOnly + appuifw.FFormDoubleSpaced
		self.form.save_hook = settings_form_save
		self.form.execute()
		if save_form:
			for i in range(len(self.form)):
				key = self.form[i][0]
				obj = self.form[i][1]
				value = self.form[i][2]
				if obj == 'combo':
					if value[1] == 1:	value = False
					else : 				value = True
				if value != pref[key]: 	pref[key] = value # set the new value if different
			write_settings(pref)						  # save everything
			audio_info_on = pref['audio_info_on']

class New_Destination_Form:
	def show(self, clear_all = False):
		global save_form
		global waypoints
		global current_waypoint

		wgs_ll = get_latlong_floats();
		if wgs_ll:
			lat = wgs_ll[0]
			long = wgs_ll[1]
		else: lat = long = 0.


		fields = [ (u'Latitude', 'float', lat), (u'Longitude', 'float', long),(u'Name', 'text', u''), (u'save', 'combo', ( [u"True", u"False"], 0)) ]

		self.form = appuifw.Form(fields,appuifw.FFormEditModeOnly)
		self.form.flags = appuifw.FFormEditModeOnly + appuifw.FFormDoubleSpaced
		self.form.save_hook = settings_form_save
		save_form = False
		self.form.execute()
		if save_form:
			# delete te current destination
			if clear_all : del waypoints[:]

			wp = (self.form[2][2], self.form[0][2],self.form[1][2]);
			waypoints.append(wp)
			current_waypoint = len(waypoints) - 1
			print self.form[3]
			if self.form[3][2][1] == 0 : # save in database
				print "Saving waypoint ", wp[0]
				add_waypoint(wp[0], wp[1], wp[2])


settings_form = SettingsForm()
new_destination_form = New_Destination_Form()

#############################################################################
class Track:
	def __init__(self, waypoints=None, from_file = None):
		global userpref
		global log_track

		if from_file:
			# close the actual log file
			if from_file == userpref["logfile"]:
				try:	del log_track # close the old log file
				except:	pass

			f = open(from_file, "r")
			lines = f.readlines()
			f.close()

			# reopen the actual log file
			if from_file == userpref["logfile"]:
				log_track = LogFile(userpref['base_dir']+'logs\\', 'track', fullname = userpref['logfile']) # open new one

			trackpoints = []
			self.coords = []
			for l in lines: trackpoints.append(l.split())
			del lines
			for t in trackpoints:
				self.coords.append(turn_llh_into_xyz(t[1],t[2],0. ,'wgs84'))
			del trackpoints
		elif waypoints:
			self.coords = []
			for w in waypoints:
				self.coords.append(turn_llh_into_xyz(w[1],w[2],0. ,'wgs84'))
		else: appuifw.note(u"Error: must provide a file name or a list of waypoints", "error")

		self.xrange = None
		self.yrange = None
		self.get_ranges()
		self.scaled = False
		self.factor = 1.
		self.xymin = [0.,0.]
		self.offset = [0.,0.]

	def __len__(self):
		return len(self.coords)

	def get_ranges(self):
		"find minimum and maximum coordinates"
		if len(self.coords) == 0:
			self.xrange = [None, None]
			self.yrange = [None, None]
			return

		self.xrange = [self.coords[0][0], self.coords[0][0]]
		self.yrange = [self.coords[0][1], self.coords[0][1]]

		for i in self.coords:
			self.xrange[0] = min(i[0], self.xrange[0])
			self.xrange[1] = max(i[0], self.xrange[1])

			self.yrange[0] = min(i[1], self.yrange[0])
			self.yrange[1] = max(i[1], self.yrange[1])

	def rescale(self,xymin = [0.,0.],  factor = 1., offset = [0,0]):
		"""	Rescales the coordinates.
				xymin is the minimum value in real coordinates
				factor is te scaling factor
				offset is the offset in screen coordinates
		"""

		if factor == 0. : return

		tmpfactor = factor / self.factor # reverse last scaling and rescale in one step

		if tmpfactor == 1. and self.offset == offset and self.xymin == xymin:
			return  # nothing happened

		# reverse scaling
		if self.scaled:
			for i in range(len(self.coords)):
				for j in [0,1]:
					self.coords[i][j] -= self.offset[j]
					self.coords[i][j] *= self.factor
					self.coords[i][j] += self.xymin[j]

		for i in range(len(self.coords)):
			for j in [0,1]:
				self.coords[i][j] -= xymin[j]
				self.coords[i][j] /= factor
				self.coords[i][j] += offset[j]
		self.factor = factor
		self.xymin = xymin
		self.offset =  offset
		self.scaled = True
#############################################################################

# This is set to 0 to request a quit
going = 1
set_value(userpref, 'disk','e:')
# Do we have an E: disk (memory card?)
## if c: is not a system drive, than better use c
if not os.path.exists('c:\\System'):
	userpref['disk'] = 'c:'

# Where we store our data and settings
set_value(userpref, 'base_dir',userpref['disk'] + '\\Apps\\NMEA_Info\\')

load_settings(userpref)		  # load the settings, from a settings file
initialize_settings() # set all key, value pairs which are not present with standard values

# disable sounds
active_profile = sysinfo.active_profile()
if not userpref['audio_info_on'] or active_profile in ['silent','meeting']:
	audio_info_on = False

class Button :
	def __init__(self, x0,y0,x1,y1, name='but'):
		self.rect = ( (x0,y0) , (x1,y1) )
		self.name = name

# touch events
touch = {}
buttons = {}
try:	buttons['track_shortest_distance'] = Image.open(userpref['base_dir'] + "img\\but_shortest_distance.png")
except:	buttons['track_shortest_distance'] = None
try:	buttons['track_shortest_distance_down'] = Image.open(userpref['base_dir'] + "img\\but_shortest_distance_down.png")
except:	buttons['track_shortest_distance_down'] = None

try:	buttons['destination_down'] = Image.open(userpref['base_dir'] + "img\\bike_down.png")
except:	buttons['destination_down'] = None
try:	buttons['destination'] = Image.open(userpref['base_dir'] + "img\\bike.png")
except:	buttons['destination'] = None

try:	buttons['pen_down'] = Image.open(userpref['base_dir'] + "img\\pen_down.png")
except:	buttons['pen_down'] = None
try:	buttons['pen'] = Image.open(userpref['base_dir'] + "img\\pen.png")
except:	buttons['pen'] = None

try: 	buttons['locked'] = Image.open(userpref['base_dir'] + "img\\locked.png")
except:	buttons['locked'] = None
try: 	buttons['locked_down'] = Image.open(userpref['base_dir'] + "img\\unlocked.png")
except:	buttons['locked_down'] = None

try: 	buttons['sound'] = Image.open(userpref['base_dir'] + "img\\sound.png")
except:	buttons['sound'] = None
try: 	buttons['sound_down'] = Image.open(userpref['base_dir'] + "img\\sound_down.png")
except:	buttons['sound_down'] = None

try: 	buttons['sound_off'] = Image.open(userpref['base_dir'] + "img\\sound_off.png")
except:	buttons['sound_off'] = None
try: 	buttons['sound_off_down'] = Image.open(userpref['base_dir'] + "img\\sound_off_down.png")
except:	buttons['sound_off_down'] = None

RGB_MIN = 0
RGB_MAX = 255
RGB_RED = (255, 0, 0)
RGB_GREEN = (0, 255, 0)
RGB_BLUE = (0, 0, 255)
RGB_LIGHT_BLUE = (65, 156, 241)
RGB_WHITE = (255, 255, 255)
RGB_GRAY = (120, 120, 120)
RGB_BLACK = (0, 0, 0)


#############################################################################

# Ensure our helper libraries are found
import sys
try:
	sys.modules['socket'] = __import__('btsocket')
except ImportError:
	pass
import socket

apid = None # active internet connection point

sys.path.append('C:/Python')
sys.path.append(userpref['disk'] + '/Python')

try:
	from geo_helper import *
except ImportError:
	appuifw.note(u"geo_helper.py module wasn't found!\nDownload at http://gagravarr.org/code/", "error")
	print "\n"
	print "Error: geo_helper.py module wasn't found\n"
	print "Please download it from http://gagravarr.org/code/ and install, before using program"
	# Try to exit without a stack trace - doesn't always work!
	sys.__excepthook__=None
	sys.excepthook=None
	sys.exit()

try:
	from OSM import *# support for Open Street Maps
	has_OSM = True
	Map = OSM_Loader(folder=userpref['base_dir'])
except ImportError:
	appuifw.note(u"OSM.py module wasn't found! Necessary for Open street map support. ", "error")
	has_OSM = False

has_pexif = None
try:
	from pexif import JpegFile
	has_pexif = True
except ImportError:
	# Will alert them later on
	has_pexif = False

has_camera = None
try:
	import camera
	has_camera = True
except ImportError:
	# Will alert them later on
	has_camera = False
except SymbianError:
	# Will alert them later on
	has_camera = False

# But positioning is built in
has_positioning = None
try:
	import positioning
	has_positioning = True
	# Big bugs in positioning still, don't use
	# (See 1842737 and 1842719 for starters)
	# SF: crashes are fixed already, satellite information could be better but it's not worth using another library
except ImportError:
	has_positioning = False

if not appuifw.touch_enabled():
		appuifw.note(u"Do you have no touch phone ? This app is optimized for touch screens, but may work", "info")


#############################################################################
# Set the screen size, and title
appuifw.app.screen=pref['app_screen']
appuifw.app.title=unicode(pref['app_title'])

# Ensure our data directory exists
if not os.path.exists(userpref['base_dir']):
	os.makedirs(userpref['base_dir'])

# make sure the logging dir exists
if not os.path.exists(userpref['base_dir']+'logs\\'):
	os.makedirs(userpref['base_dir']+ 'logs\\')
#############################################################################

class mean_value:
	"compute the mean value of a set of values. Only a maximum of values is used (moving average). "
	def __init__(self, max_values = 10):
		self.max = max_values
		self.val = []
		self.items = 0

	def append(self, value):
		if self.items < self.max:
			self.val.append(value)
			self.items += 1
		else:
			del self.val[0]
			self.val.append(value)

	def mean(self):
		if self.items == 0: return None
		sum = 0
		for i in self.val:
			sum += i
		sum /= float(self.items)
		return float(sum)

	def resize(self, new_max):
		"Sets a new size for a new max value"
		self.max = new_max
		if self.items <= self.max:
			return
		elif self.items > self.max:
			while len(self.val) > self.max: del self.val[0]
		return

	def clear(self):
		self.items = 0
		del self.val
		self.val = []


info = {} # used to store a lot of information
info['position_lat_avg'] = mean_value(5)
info['position_long_avg'] = mean_value(5)
info['speed_avg'] = mean_value(20)

def format_distance(value):
	"formats distances humand readable in reasonable units"
	if value > 100000:
		return "%4d km" % (value/1000.0)
	elif value < 2000:
		return "%4d m" % value
	else:
		return "%3.02f km" % (value/1000.0)

def format_audio_number(value):
	"""Formats integer and floating point values for text to speech.
	The language is GERMAN."""
	str_dist = str(value)
	if str_dist.find('.') != -1:
		parts = str_dist.split('.')
	else:
		parts = [str_dist, None]

	digits = []
	if len(parts[0]) > 0:
		for i in str_dist: digits.append(i)

	message = ''
	if len(parts[0]) > 0 and len(parts) < 5:
		if len(parts[0]) == 4:
			if not parts[0][0] in ' 1' :	message += parts[0][0]
			if parts[0][0] != ' ' :			message += 'tausend '
			parts[0] = parts[0][1:]

		if len(parts[0]) == 3:
			if not parts[0][0] in ' 1':	message += parts[0][0]
			message += 'hundert '
			parts[0] = parts[0][1:]

		if len(parts[0]) == 2:
			if parts[0][0] == '1':
				if parts[0][0] == '0': message += "zehn"
				if parts[0][0] == '1': message += "elf"
				if parts[0][0] == '2': message += "zwoelf"
				if parts[0][0] == '3': message += "dreizehn"
				if parts[0][0] == '4': message += "vierzehn"
				if parts[0][0] == '5': message += "fuenfzehn"
				if parts[0][0] == '6': message += "sechzehn"
				if parts[0][0] == '7': message += "siebzehn"
				if parts[0][0] == '8': message += "achtzehn"
				if parts[0][0] == '9': message += "neunzehn"
			elif parts[0][1] != '0':
				if parts[0][1] == '1':	message += "ein und "
				else:					message += parts[0][1] + 'und '
				if parts[0][0] == '2': message += 'zwanzig'
				if parts[0][0] == '3': message += 'dreissig'
				if parts[0][0] == '4': message += 'vierzig'
				if parts[0][0] == '5': message += 'fuenfzig'
				if parts[0][0] == '6': message += 'sechzig'
				if parts[0][0] == '7': message += 'siebzig'
				if parts[0][0] == '8': message += 'achtzig'
				if parts[0][0] == '9': message += 'neunzig'
		else: # only 1 digit
			message += parts[0][0]
	elif len(parts[0]) > 4:
		message += parts[0]
	elif len(parts[0]) == 0:
		message += 'Null'

	if parts[1] and len(parts[1]) > 0 :
		message += ' Komma ' + parts[1]
	return message

def format_distance_speech(value):
	"Same as format_distance but opimized for text-to-speech."
	if value:
		dist = None
		unit = "meter"

		if value > 100000:
			dist = "%4d" % (value/1000.0)
			unit = "Kilometer"
		elif value < 2000:
			dist = "%4d" % value
			unit = "Meter"
		else:
			dist = "%3.02f" % (value/1000.0)
			unit = "Kilometer"

		message = format_audio_number(dist)

		message += ' ' + unit

		dist = 'noch ' + message
		return dist
	return None

def set_audio_alert_placetime():
	"Saves place and time of the last text-to-speech-event."
	global place_of_last_audio_alert
	global time_last_audio_message
	global info
	time_last_audio_message = time.time()
	#wgs_ll = get_latlong_floats()
	#if wgs_ll != None:
	if info.has_key('avg_position') and info['avg_position'] != None:
		place_of_last_audio_alert = info['avg_position']


def audio_direction_info():
	"... gives direction warnings"
	global speaking

	set_audio_alert_placetime()

	speaking = True
	diff = info['proposed_direction']
	if diff > 25 and diff <= 55:
		audio.say(u'Leicht links halten bitte.')
	elif diff > 55 and diff <= 135:
		audio.say(u'Links halten bitte.')
	elif diff > 135 and diff < 225:
		audio.say(u'Umdrehen bitte.')
	elif diff >= 225 and diff < 305:
		audio.say(u'Rechts halten bitte.')
	elif diff >= 305 and diff < 335:
		audio.say(u'Leicht rechts halten bitte.')
	else:
		audio.say(u'Immer schoen geradeaus.')
	speaking = False

def audio_info():
	"gives full audio information"
	global speaking
	global time_last_audio_message

	set_audio_alert_placetime()

	speaking = True

	if location['valid'] == 0:
		audio.say(u'Kein gültiges GPS-Signal')

	if info.has_key('dist'):
		dist = format_distance_speech(info['dist'])
		audio.say(u'%s'% dist)

	if info.has_key('bearing'):
		try:	angle = float(info['bearing'])
		except: angle = None

		if angle:
			sentence = u'Das Ziel befindet sich im '
			if angle > 337.5 or angle < 22.5 :
				sentence += u"Norden."
			elif angle >= 22.5 and angle < 67.5 :
				sentence += u"Nord-Osten."
			elif angle >= 67.5 and angle < 112.5 :
				sentence += u"Osten."
			elif angle >= 112.5 and angle < 157.5 :
				sentence += u"Süd-Osten."
			elif angle >= 157.5 and angle < 202.5 :
				sentence += u"Süden."
			elif angle >= 202.5 and angle < 247.5 :
				sentence += u"Sued-Westen."
			elif angle >= 247.5 and angle < 292.5 :
				sentence += u"Westen."
			elif angle >= 292.5 and angle < 337.5 :
				sentence += u"Nord-Westen."
			audio.say(sentence)
	if location['valid'] == 1:
		# tell the direction (only if I move)
		if info.has_key('speed_avg') and info['speed_avg'].items > 0 \
		and info['speed_avg'].mean() > userpref['minimum_speed_mps'] \
		and info.has_key('proposed_direction'):
			audio_direction_info()

	speaking = False

def select_closest_waypoint():
	"""Checks all waypoints and sets current_waypoint to that one
	which is closest to the GPS location"""
	global shortest_waypoint
	global current_waypoint

	if location['valid'] == 1:
		wgs_ll = get_latlong_floats()
		if wgs_ll != None:
			wgs_lat = wgs_ll[0]
			wgs_lon = wgs_ll[1]
	else:
		appuifw.note(u"GPS location invalid\n Using last valid value.", 'info')
		try:	wgs_lat = info['last_avg_position'][0]
		except:	wgs_lat = None
		try:	wgs_lon = info['last_avg_position'][1]
		except: wgs_lon = None

	if not (wgs_lat or wgs_lon):
		appuifw.note(u"Found no valid GPS location.", 'error')
		return

	shortest_distance = None
	for w in range(len(waypoints)):
		w_lat = waypoints[w][1]
		w_lon = waypoints[w][2]

		res = calculate_distance_and_bearing(w_lat, w_lon, wgs_lat, wgs_lon)
		distance, direction = dist_tupel_to_floats(res)
		if shortest_distance == None or distance < shortest_distance:
			shortest_distance = distance
			current_waypoint = w

	appuifw.note(u"Closest waypoint is %d." % current_waypoint, 'info')
	return

def get_next_turning_info(assume_on_track = False):
	"""Computes the angle between the direction towards the next
	waypoint and the direction to next but one waypoint.
	Return an angle > 0. when the turning direction is right
	and < 0. if it is left
	assume_on_track = True means the moving direction is computed
	from the track not from measured data"""
	global current_waypoint
	global waypoints

	if current_waypoint == None:
		return None

	start = waypoints[current_waypoint]

	old_direction = None
	if not assume_on_track and info.has_key('avg_heading'): # use moving direction if present
		old_direction = info['avg_heading']
	else:
		if current_waypoint > 0:
			last = waypoints[current_waypoint - 1]
			dist = calculate_distance_and_bearing(last[1],last[2], start[1],start[2])
			distance, old_direction = dist_tupel_to_floats(dist)

	new_direction = None
	if current_waypoint < len(waypoints) - 1:
		next = waypoints[current_waypoint + 1]
		dist = calculate_distance_and_bearing(start[1],start[2], next[1], next[2])
		distance, new_direction = dist_tupel_to_floats(dist)

	# return direction difference only, when it is greater then the threshold value
	if old_direction != None and new_direction != None:
		diff = old_direction - new_direction
		if diff < 0 : diff += 360
		if abs(diff) > userpref['min_direction_difference']:
			return diff - 180. # if > 0 turn right, else left
	return None

def select_next_waypoint():
	"""Searches the next upcoming waypoint which can be reached on a straight
	line and returns the direction which has to be chosen at the
	actual GPS position """
	global current_waypoint
	global waypoints

	start = waypoints[current_waypoint]

	old_direction = None
	if info.has_key('avg_heading'): # use moving direction if present
		old_direction = info['avg_heading']
	elif current_waypoint > 0:
		last = waypoints[current_waypoint - 1]
		dist = calculate_distance_and_bearing(last[1],last[2], start[1],start[2])
		distance, old_direction = dist_tupel_to_floats(dist)

	first_direction = None
	mean_direction = None
	p2p_dist = 0.0
	selection = None
	if len(waypoints) > current_waypoint + 1 :
		for w in range(current_waypoint+1, len(waypoints)):
			tmp1 = waypoints[w-1]
			tmp2 = waypoints[w]
			dist = calculate_distance_and_bearing(tmp1[1], tmp1[2], tmp2[1], tmp2[2])
			distance, direction = dist_tupel_to_floats(dist)

			# if this is the last waypoint and loop did not break, then select this one
			if w == len(waypoints) -1:
				selection = w
				break

			if first_direction == None:						# save the direction
				first_direction = direction
				mean_direction = direction
				p2p_dist = distance
			else:
				if abs(mean_direction - direction) < userpref['min_direction_difference']  :   # if directions differ only by max. 10 degrees
					mean_direction += direction		# compute the mean value
					mean_direction /= 2
					p2p_dist += distance
					continue						# and check the next waypoint
				else:
					selection = w - 1				# else save the last waypoint which lies on a straight line to the waypoint we where last
					break

		if selection:
			current_waypoint = selection
		else: # not found any matching waypoint, must take the next point
			current_waypoint += 1



		compute_positional_data() # update direction info

		# return direction difference only, when it is greater then the threshold value
		if old_direction != None and mean_direction != None:
			diff = old_direction - mean_direction
			if diff < 0 : diff += 360
			if abs(diff) > userpref['min_direction_difference']:
				return diff - 180., p2p_dist # if > 0 turn right, else left

	return None, None # nothing done

#def select_next_waypoint():
	#"""Searches the next upcoming waypoint which can be reached on a straight
	#line and returns the direction which has to be chosen at the
	#actual GPS position """
	#global current_waypoint
	#global waypoints

	#start = waypoints[current_waypoint]

	#old_direction = None
	#if info.has_key('avg_heading'): # use moving direction if present
		#old_direction = info['avg_heading']
	#elif current_waypoint > 0:
		#last = waypoints[current_waypoint - 1]
		#dist = calculate_distance_and_bearing(last[1],last[2], start[1],start[2])
		#distance, old_direction = dist_tupel_to_floats(dist)

	#first_direction = None
	#mean_direction = None
	#selection = None
	#if len(waypoints) > current_waypoint + 1 :
		#for w in range(current_waypoint+1, len(waypoints)):
			#tmp1 = waypoints[w-1]
			#tmp2 = waypoints[w]
			#dist = calculate_distance_and_bearing(tmp1[1], tmp1[2], tmp2[1], tmp2[2])
			#distance, direction = dist_tupel_to_floats(dist)

			## if this is the last waypoint and loop did not break, then select this one
			#if w == len(waypoints) -1:
				#selection = w
				#break

			#if first_direction == None:						# save the direction
				#first_direction = direction
				#mean_direction = direction
			#else:
				#if abs(mean_direction - direction) < userpref['min_direction_difference']  :   # if directions differ only by max. 10 degrees
					#mean_direction += direction		# compute the mean value
					#mean_direction /= 2
					#continue						# and check the next waypoint
				#else:
					#selection = w - 1				# else save the last waypoint which lies on a straight line to the waypoint we where last
					#break

		#if selection:
			#current_waypoint = selection
		#else: # not found any matching waypoint, must take the next point
			#current_waypoint += 1

		#compute_positional_data() # update direction info

		## return direction difference only, when it is greater then the threshold value
		#if old_direction != None and mean_direction != None:# and diff > pref['min_direction_difference']:
			#diff = old_direction - mean_direction
			#if diff < 0 : diff += 360
			#if abs(diff) > userpref['min_direction_difference']:
				#return diff - 180. # if > 0 turn right, else left

	#return None # nothing done#~

def select_prev_waypoint():
	"""Searches the next upcoming waypoint which can be reached on a straight
	line and returns the direction which has to be chosen at the
	actual GPS position """
	global current_waypoint
	global waypoints

	first_direction = None
	mean_direction = None
	selection = None
	if current_waypoint > 0:
		for w in range(current_waypoint-1, 0, -1):
			tmp1 = waypoints[w+1]
			tmp2 = waypoints[w]
			dist = calculate_distance_and_bearing(tmp1[1], tmp1[2], tmp2[1], tmp2[2])
			distance, direction = dist_tupel_to_floats(dist)

			# if this is the first waypoint and loop did not break, then select this one
			if w == 0:
				selection = w
				break

			if first_direction == None:						# save the direction
				first_direction = direction
				mean_direction = direction
			else:
				if abs(mean_direction - direction) < userpref['min_direction_difference']  :   # if directions differ only by max. 10 degrees
					mean_direction += direction		# compute the mean value
					mean_direction /= 2
					continue						# and check the next waypoint
				else:
					selection = w + 1				# else save the last waypoint which lies on a straight line to the waypoint we where last
					break

		if selection:
			current_waypoint = selection
		else: # not found any matching waypoint, must take the next point
			current_waypoint -= 1

		compute_positional_data() # update direction info

	return None # nothing done

def speech_timer():
	"Function for the speech timer - informs the user of important data. Runs as seperate thread, otherwise the application crashes - why that ?"
	global going
	global time_last_audio_message, place_of_last_audio_alert
	global waypoints, current_waypoint
	global userpref

	while going > 0 and current_waypoint != None:
		try:
			warning_dist = 100.
			# approaching waypoint
			if info.has_key('dist') and (info['dist'] < warning_dist)\
				and current_waypoint < len(waypoints) -1\
				and ((not info.has_key('150m_warning')) or info["150m_warning"] != current_waypoint):
					dist_to_next_wp = int(info['dist'])
					info['150m_warning'] = current_waypoint # important: set this value here, because current_waypoint is chnaged in the next line
					lr, p2p = select_next_waypoint()						 # otherwise choose next waypoint
					if lr != None:
						dir = "rechts"
						if lr < 0.:	dir = "links"
						if audio_info_on:
							d = format_audio_number(dist_to_next_wp)
							audio.say("In %s Metern %s abbiegen." % (d,dir))
							if (p2p < warning_dist):
								lrn = get_next_turning_info(assume_on_track=True)
								if lrn != None:
									dir = "rechts"
									if lrn < 0.:	dir = "links"
									p2pd = format_audio_number(int(p2p))
									audio.say("Dann nach %s Metern %s." % (p2pd,dir))


			elif info.has_key('dist') and (info['dist'] <= 40.)\
				 and current_waypoint == len(waypoints) -1 :	# waypoint reached, this may be the destination itself
					if audio_info_on: audio.say("Du bist am Ziel angekommen.")
					current_waypoint = None   # stop navigation
					del info['dist']		# clear distance value
				#elif current_waypoint < len(waypoints) -1:
					##new_direction = select_next_waypoint()						 # otherwise choose next waypoint
					##if audio_info_on: audio.say("Du hast einen Wegpunkt erreicht.")
					### comment on this : Since we navigate only to waypoints
					### with a changing routing direction, every next
					### step has to be announced as turning point except
					### the last one
					##if current_waypoint != len(waypoints) -1 and new_direction != None:
						##if audio_info_on:
							##if new_direction > 0.:
								##audio.say("Abbiegung rechts !")
							##elif new_direction < 0.:
								##audio.say("Abbiegung links !")

					#try: del info['150m_warning']
					#except: pass

			# alert when direction is totally wrong and distance from last point is larger than 40m
			elif audio_info_on and info.has_key('speed_avg') and info['speed_avg'].items > 0 \
				and info['speed_avg'].mean() > userpref['minimum_speed_mps'] and info.has_key('proposed_direction') \
				and (time.time() - time_last_audio_message) >= userpref['audio_alert_interval']:
				wgs_ll = get_latlong_floats();
				if wgs_ll != None and place_of_last_audio_alert != None:
					try:
						dist = calculate_distance_and_bearing(	place_of_last_audio_alert[0], place_of_last_audio_alert[1],\
																wgs_ll[0], wgs_ll[1])
					except:
						dist = None

					distance, direction = dist_tupel_to_floats(dist)
					if distance != None and distance >= userpref['minimum_warning_distance'] :
						dir = info['proposed_direction']
						if dir > 40. and dir < 320.: audio_direction_info() # alert if the actual direction is bad

			elif audio_info_on and (time.time() - time_last_audio_message) > userpref['audio_info_interval']: # normal audio alert interval
				audio_info() #

		except SymbianError, e :		# if speaking is not allowed at the moment
			if not e.errno in [-13,-21] : raise	# if it was another exception, then raise again

		e32.ao_sleep(1); #  check only once per second

def calc_line(radius,angle,centre):
	"""Computes a line that starts in the centre of a circle an end on the border - so radius and angle
	define the line length and direction, while centre is a tuple giving (x,y) of the screen-coordinates. """
	rads = float( angle ) / 360.0 * 2.0 * math.pi
	radius = float(radius)
	t_x = radius * math.sin(rads) + centre[0]
	t_y = -1.0 * radius * math.cos(rads) + centre[1]
	b_x = radius * math.sin(rads + math.pi) + centre[0]
	b_y = -1.0 * radius * math.cos(rads + math.pi) + centre[1]
	return (t_x,t_y,b_x,b_y)
################################################################################

waypoints = []			# used to store the current track
current_waypoint = 0	# the index of the waypoint which is approached starting with 0

# Path to DB needs to be in unicode
pref['waypoints_db'] = unicode(pref['waypoints_db'])

def open_waypoints_db():
	"""Open the waypoints DB file, creating if needed"""
	global prefs

	db = e32db.Dbms()
	try:
		db.open(pref['waypoints_db'])
	except:
		# Doesn't exist yet
		db.create(pref['waypoints_db'])
		db.open(pref['waypoints_db'])
		db.execute(u"CREATE TABLE waypoints (name VARCHAR, lat FLOAT, long FLOAT, added TIMESTAMP)")
	return db

def add_waypoint(name,lat,long):
	"""Adds a waypoint to the database"""
	global waypoints
	global current_waypoint

	# Escape the name
	name = name.replace(u"'",u"`")

	# Add to the db
	db = open_waypoints_db()
	sql = "INSERT INTO waypoints (name,lat,long,added) VALUES ('%s',%f,%f,#%s#)" % ( name, lat, long, e32db.format_time(time.time()) )
	#print sql
	db.execute( unicode(sql) )
	db.close()

	# We would update the waypoints array, but that seems to cause a
	#  s60 python crash!
	##waypoints.append( (unicode(name), lat, long) )
	##current_waypoint = len(waypoints) - 1
	current_waypoint = -1

def delete_current_waypoint():
	"""Deletes the current waypoint from the database"""
	global waypoints
	global current_waypoint

	if current_waypoint == 0:
		return
	name = waypoints[current_waypoint][0]

	# Delete from the array
	for waypoint in waypoints:
		if waypoint[0] == name:
			waypoints.remove(waypoint)
	current_waypoint = 0

	# Delete from the db
	db = open_waypoints_db()
	sql = "DELETE FROM waypoints WHERE name='%s'" % ( name )
	print sql
	db.execute( unicode(sql) )
	db.close()

def load_destination_db():
	"""Loads our direction-of waypoints"""
	global waypoints
	global current_waypoint
	list = []
	# Now load from disk
	db = open_waypoints_db()
	dbv = e32db.Db_view()
	dbv.prepare(db, u"SELECT name, lat, long FROM waypoints ORDER BY name ASC")
	dbv.first_line()
	for i in range(dbv.count_line()):
		dbv.get_line()
		list.append( (dbv.col(1), dbv.col(2), dbv.col(3)) )
		dbv.next_line()
	db.close()

	return list

def import_gpx_track():
	global waypoints
	global current_waypoint

	# import gpx_tracks
	gpx_file_name = userpref['base_dir'] + "track.gpx"
	if not os.path.exists(gpx_file_name):
		# First up, go with the default
		waypoints = []
		waypoints.append( (pref['direction_of_name'],pref['direction_of_lat'],pref['direction_of_long']) )
		return False

	file = open(gpx_file_name, "r")
	lines = file.readlines()
	file.close()

	counter = 0
	for l in lines:
		l = l.strip()
		if l.strip().startswith('<trkpt'):
			# example line: <trkpt lat="52.51375280" lon="13.45492600">
			splits = l.split('"')
			for s in range(len(splits)):
				try:
					if splits[s].endswith('lat='):lat = float(splits[s+1])
				except: lat = None
				try:
					if splits[s].endswith('lon='):lon = float(splits[s+1])
				except: lon = None
			if lat and lon:
				counter += 1
				desc = "(Waypoint %d)" % counter
			if pref['use_db']:
				add_waypoint(desc, lat, lon)
			waypoints.append( (desc,lat,lon) )

	del lines
	current_waypoint = 0
	appuifw.note(u'Gpx track imported : %d waypoints.'% (len(waypoints)),"info")

#	online_query = appuifw.query(u"Download maps for the track ?", "query")
#	if online_query == True: # load all maps
#		#zoomvalue = 14
#		mapinfo = []
#		### Setup AP
#		apid = socket.select_access_point()
#		apo = socket.access_point(apid)
#		socket.set_default_access_point(apo)
#		#### Start connection
#		apo.start()
#		###get the maps
#		for zoomvalue in range(19):
#			for w in waypoints:
#				res = Map.get_map(w[1],w[2],zoomvalue)
#				if not res in mapinfo:	mapinfo.append(res)
#
#		### Stop connection
#		apo.stop()


#	w = waypoints[0]
#	fname = Map.get_map(w[1],w[2],11)[0]
#	map_img = Image.open(fname)

	return True
	#file = open("track.csv", "w")
	#for w in waypoints:
		#print w
		#file.write("%s\t%s\t%s\n" % (w[0], w[1], w[2]))
	#file.close()

# Load our direction-of waypoints
if not import_gpx_track(): appuifw.note(u"Could not load track", "error")
waypoints_xy = Track(waypoints)

#############################################################################

# Our current location
location = {}
location['valid'] = 1 # Default to valid, in case no GGA/GLL sentences
# Our current motion
motion = {}
# What satellites we're seeing
satellites = {}
# Warnings / errors
disp_notices = ''
disp_notices_count = 0
# Our logging parameters
log_interval = 0
debug_log_fh = ''
gsm_log_fh = ''
# Photo parameters
all_photo_sizes = None
photo_size = None
preview_photo = None
# How many times have we shown the current preview?
photo_displays = 0
# Are we currently (in need of) taking a preview photo?
taking_photo = 0
#
time_last_audio_message = 0.
place_of_last_audio_alert = None
speaking = False

#############################################################################

# Generate the checksum for some data
# (Checksum is all the data XOR'd, then turned into hex)
def generate_checksum(data):
	"""Generate the NMEA checksum for the supplied data"""
	csum = 0
	for c in data:
		csum = csum ^ ord(c)
	hex_csum = "%02x" % csum
	return hex_csum.upper()

# Format a NMEA timestamp into something friendly
def format_time(time):
	"""Generate a friendly form of an NMEA timestamp"""
	hh = time[0:2]
	mm = time[2:4]
	ss = time[4:]
	return "%s:%s:%s UTC" % (hh,mm,ss)

# Format a NMEA date into something friendly
def format_date(date):
	"""Generate a friendly form of an NMEA date"""
	dd = int(date[0:2])
	mm = int(date[2:4])
	yy = int(date[4:6])
	yyyy = yy + 2000
	return format_date_from_parts(yyyy,mm,dd)

def format_date_from_parts(yyyy,mm,dd):
	"""Generate a friendly date from yyyy,mm,dd"""
	months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
	return "%02d %s %d" % (dd, months[(int(mm)-1)], yyyy)

def nmea_format_latlong(lat,long):
	"""Turn lat + long into nmea format"""

	def format_ll(hour_digits,ll):
		abs_ll = abs(ll)
		hour_ll = int(abs_ll)
		min_ll = (abs_ll - hour_ll) * 60
		# 4dp, so *10,000
		str_ll = "%03d%02d.%04d" % ( hour_ll, int(min_ll), 10000*(min_ll-int(min_ll)) )
		if hour_digits == 2 and str_ll[0] == '0':
			str_ll = str_ll[1:]
		return str_ll

	if str(lat).lower() == 'nan':
		flat = '0000.0000,N'
	else:
		flat = format_ll(2, lat) + ","
		if lat < 0:
			flat += "S"
		else:
			flat += "N"

	if str(long).lower() == 'nan':
		flong = '00000.0000,E'
	else:
		flong = format_ll(3, long) + ","
		if long < 0:
			flong += "W"
		else:
			flong += "E"
	return (flat,flong)

def user_format_latlong(lat,long):
	"""Turn lat + long into a user facing format"""
	if str(lat) == 'NaN':
		flat = '00:00:00N'
	else:
		alat = abs(lat)
		mins = (alat-int(alat))*60
		secs = (mins-int(mins))*60
		flat = "%02d:%02d:%02d" % (int(alat),int(mins),int(secs))
		if lat < 0:
			flat += "S"
		else:
			flat += "N"
	if str(long) == 'NaN':
		flong = '000:00:00W'
	else:
		along = abs(long)
		mins = (along-int(along))*60
		secs = (mins-int(mins))*60
		flong = "%03d:%02d:%02d" % (int(along),int(mins),int(secs))
		if long < 0:
			flong += "W"
		else:
			flong += "E"
	return (flat,flong)

# NMEA data is HHMM.nnnn where nnnn is decimal part of second
def format_latlong(data):
	"""Turn HHMM.nnnn into HH:MM.SS"""

	# Check to see if it's HMM.nnnn or HHMM.nnnn or HHHMM.nnnn
	if data[5:6] == '.':
		# It's HHHMM.nnnn
		hh_mm = data[0:3] + ":" + data[3:5]
		dddd = data[6:]
	elif data[3:4] == '.':
		# It's HMM.nnnn
		hh_mm = data[0:1] + ":" + data[1:3]
		dddd = data[4:]
	else:
		# Assume HHMM.nnnn
		hh_mm = data[0:2] + ":" + data[2:4]
		dddd = data[5:]

	# Turn from decimal into seconds, and strip off last 2 digits
	sec = int( float(dddd) / 100.0 * 60.0 / 100.0 )
	return hh_mm + ":" + str(sec)

def format_latlong_dec(data):
	"""Turn HHMM.nnnn into HH.ddddd"""

	# Check to see if it's HMM.nnnn or HHMM.nnnn or HHHMM.nnnn
	if data[5:6] == '.':
		hours = data[0:3]
		mins = float(data[3:])
	elif data[3:4] == '.':
		hours = data[0:1]
		mins = float(data[1:])
	else:
		hours = data[0:2]
		mins = float(data[2:])

	dec = mins / 60.0 * 100.0
	# Cap at 6 digits - currently nn.nnnnnnnn
	dec = dec * 10000.0
	str_dec = "%06d" % dec
	return hours + "." + str_dec

def get_latlong_floats():
	"Removes N/S E/W and replace S and W by '-' "
	global location
	if not location.has_key('lat_dec') or not location.has_key('long_dec'):
		return None

	if location['valid'] == 0: return None

	wgs_lat = location['lat_dec'];
	wgs_long = location['long_dec'];
	if wgs_lat[-1:] == 'S':
		wgs_lat = '-' + wgs_lat;
	if wgs_long[-1:] == 'W':
		wgs_long = '-' + wgs_long;

	#print wgs_lat, wgs_long
	try:
		wgs_lat = float(wgs_lat[0:-1])
		wgs_long = float(wgs_long[0:-1])
	except ValueError:
		return None
	return (wgs_lat,wgs_long)

def dist_tupel_to_floats(dist):

	if dist == None : return None, None

	try:
		distance = float(dist[0])
	except ValueError:
		distance = None

	try:
		direction = float(dist[1])
		if direction < 0.: direction += 360.
	except ValueError:
		direction = None
	return distance, direction

#############################################################################

def readline(sock):
	"""Read one single line from the socket"""
	line = ""
	while 1:
		char = sock.recv(1)
		if not char: break
		line += char
		if char == "\n": break
	return line

#############################################################################

def do_gga_location(data):
	"""Get the location from a GGA sentence"""
	global location

	# TODO: Detect if we're not getting speed containing sentences, but
	#		we are geting location ones, so we need to compute the speed
	#		for ourselves

	d = data.split(',')
	location['type'] = 'GGA'
	location['lat'] = "%s%s" % (format_latlong(d[1]),d[2])
	location['long'] = "%s%s" % (format_latlong(d[3]),d[4])
	location['lat_dec'] = "%s%s" % (format_latlong_dec(d[1]),d[2])
	location['long_dec'] = "%s%s" % (format_latlong_dec(d[3]),d[4])
	location['lat_raw'] = "%s%s" % (d[1],d[2])
	location['long_raw'] = "%s%s" % (d[3],d[4])
	location['alt'] = "%s %s" % (d[8],d[9])
	location['time'] = format_time(d[0])
	location['tsecs'] = long(time.time())
	if d[5] == '0':
		location['valid'] = 0
	else:
		location['valid'] = 1

def do_gll_location(data):
	"""Get the location from a GLL sentence"""
	global location

	d = data.split(',')
	location['type'] = 'GLL'
	location['lat'] = "%s%s" % (format_latlong(d[0]),d[1])
	location['long'] = "%s%s" % (format_latlong(d[2]),d[3])
	location['lat_dec'] = "%s%s" % (format_latlong_dec(d[0]),d[1])
	location['long_dec'] = "%s%s" % (format_latlong_dec(d[2]),d[3])
	location['lat_raw'] = "%s%s" % (d[0],d[1])
	location['long_raw'] = "%s%s" % (d[2],d[3])
	location['time'] = format_time(d[4])
	if d[5] == 'A':
		location['valid'] = 1
	elif d[5] == 'V':
		location['valid'] = 0

def do_rmc_location(data):
	"""Get the location from a RMC sentence"""
	global location

	d = data.split(',')
	location['type'] = 'RMC'
	location['lat'] = "%s%s" % (format_latlong(d[2]),d[3])
	location['long'] = "%s%s" % (format_latlong(d[4]),d[5])
	location['lat_dec'] = "%s%s" % (format_latlong_dec(d[2]),d[3])
	location['long_dec'] = "%s%s" % (format_latlong_dec(d[4]),d[5])
	location['lat_raw'] = "%s%s" % (d[2],d[3])
	location['long_raw'] = "%s%s" % (d[4],d[5])
	location['time'] = format_time(d[0])

#############################################################################

def do_gsv_satellite_view(data):
	"""Get the list of satellites we can see from a GSV sentence"""
	global satellites
	d = data.split(',')

	# Are we starting a new set of sentences, or continuing one?
	full_view_in = d[0]
	sentence_no = d[1]
	tot_in_view = d[2]

	if int(sentence_no) == 1:
		satellites['building_list'] = []

	# Loop over the satellites in the sentence, grabbing their data
	sats = d[3:]
	while len(sats) > 0:
		prn_num = sats[0]
		elevation = float(sats[1])
		azimuth = float(sats[2])
		sig_strength = float(sats[3])

		satellites[prn_num] = {
			'prn':prn_num,
			'elevation':elevation,
			'azimuth':azimuth,
			'sig_strength':sig_strength
		}

		satellites['building_list'].append(prn_num)
		sats = sats[4:]

	# Have we got all the details from this set?
	if sentence_no == full_view_in:
		satellites['in_view'] = satellites['building_list']
		satellites['in_view'].sort()
		satellites['building_list'] = []
	# All done

def do_gsa_satellites_used(data):
	"""Get the list of satellites we are using to get the fix"""
	global satellites
	d = data.split(',')

	sats = d[2:13]
	overall_dop = d[14]
	horiz_dop = d[15]
	vert_dop = d[16]

	while (len(sats) > 0) and (not sats[-1]):
		sats.pop()

	satellites['in_use'] = sats
	satellites['in_use'].sort()
	satellites['overall_dop'] = overall_dop
	satellites['horiz_dop'] = horiz_dop
	satellites['vert_dop'] = vert_dop

def do_vtg_motion(data):
	"""Get the current motion, from the VTG sentence"""
	global motion
	d = data.split(',')

	if not len(d[6]):
		d[6] = 0.0
	motion['speed_kmph'] = float(d[6])
	motion['speed_mph'] = float(d[6]) / 1.609344
	motion['true_heading'] = d[0]

	motion['mag_heading'] = ''
	if d[2] and int(d[2]) > 0:
		motion['mag_heading'] = d[2]

#############################################################################
def process_positioning_update(data):
	"""Process a location update from the Python Positioning module"""
	global satellites
	global location
	global motion
	global gps

	latlong = (0,0)

	if data.has_key("position"):
		pos = data["position"]
		latlong = user_format_latlong(pos["latitude"], pos["longitude"])
		location['lat']  = latlong[0]
		location['long']  = latlong[1]

		if str(pos["latitude"]).lower() == 'nan':
			location['lat_dec'] = None
			location['valid'] = 0
		else:
			location['lat_dec'] = "%02.6f" % pos["latitude"]
			location['valid'] = 1

		if str(pos["longitude"]).lower() == 'nan':
			location['long_dec'] = None
		else:
			location['long_dec'] = "%02.6f" % pos["longitude"]

		location['alt'] = "%3.1f m" % (pos["altitude"])

		satellites['horiz_dop'] = "%0.1f" % pos["horizontal_accuracy"]
		satellites['vert_dop'] = "%0.1f"  % pos["vertical_accuracy"]
		satellites['overall_dop'] = "%0.1f" % ((pos["horizontal_accuracy"]+pos["vertical_accuracy"])/2)

	if data.has_key("course"):
		cor = data["course"]
		if str(cor["speed"]).lower() == 'nan':
			if motion.has_key('speed'):
				del motion['speed']
		else:
			# symbian gps speed is in meters per second
			mps = cor["speed"]
			motion['speed'] = mps
			motion['speed_kmph'] = mps / 1000.0 * 60 * 60
			motion['speed_mph'] = motion['speed_kmph'] / 1.609344

		if str(cor["heading"]).lower() == 'nan':
			if motion.has_key('true_heading'): del motion['true_heading']
			if motion.has_key('heading'): del motion['heading']
		else:
			motion['heading'] = cor['heading']
			motion['true_heading'] = "%0.1f" % cor["heading"]

	if data.has_key("satellites"):
		sats = data["satellites"]
		#print sats
		# We don't yet get data on the satellites, just the numbers
		satellites['in_view'] = ["??" for prn in range(sats['satellites'])]
		satellites['in_use']  = ["??" for prn in range(sats['used_satellites'])]

		location['tsecs'] = sats["time"]
		try:
			timeparts = time.gmtime( location['tsecs'] )
		except ValueError:
			timeparts = None

		if timeparts == None: return
		location['time'] = "%02d:%02d:%02d" % (timeparts[3:6])
		location['date'] = format_date_from_parts(*timeparts[0:3])

		return


#############################################################################
class LogFile:
	def __init__(self, basepath, name, fullname = None):
		self.path = basepath
		self.name = name
		self.file = None
		self.logtime = None
		self.fullpath = None
		if fullname == None:
			self.set_new_filename()
		else:
			self.fullpath = fullname
		self.open()
		print "log: ",self.fullpath

	def __del__(self):
		if self.file != None:
			self.file.flush()
			self.file.close()
			self.file = None

	def set_new_filename(self):
		datetimestr = time.strftime(self.name + "_%Y%m%d_%H%M%S.log", time.localtime(time.time()))
		self.fullpath = os.path.join(self.path, datetimestr)
		return

	def open(self, mode="a"):
		if self.fullpath :
			self.file = open(self.fullpath, mode)

	def log(self, obj):
		if type(obj) == type("string"):
			msg = str.strip() + '\n'
			self.file.write(msg)
		elif type(obj) == type([1,2,3]): # type is a list, then make tsv-file
			msg = ""
			for i in obj: msg += str(i) + '\t'
			msg = msg.rstrip()
			msg += '\n'
			self.file.write(msg)
		self.logtime = time.localtime()

def save_gga_log(rawdata = None):
	global satellites
	global location
	global motion
	global log_track

	if pref['gsmloc_logging']:
		gsm_stumblestore_log()

	if rawdata != None:
		log_track.log(rawdata)
		return

	height = 0
	if location['valid'] == 0: # log position everything to a file
		height = pos["altitude"]
		pos = data['position']
		latlong = nmea_format_latlong(pos['latitude'],pos['longitude'])
		try:
			timeparts = time.gmtime( location['tsecs'] )
		except ValueError:
			timeparts = None
		gga_time = "%02d%02d%02d.%02d" % (timeparts[3:7])
		# Fake a GGA sentence, so we can log if required
		fake_gga = "$GPGGA,%s,%s,%s,%d,%02d,0.0,%0.2f,M,,,,\n" % \
			(gga_time,latlong[0],latlong[1],location['valid'], len(satellites['in_view']),height)
		#gga_log(fake_gga)
		log_track.log(fake_gga)

def init_debug_log():
	"""Initialise the debug log, using pref information"""
	global pref
	global debug_log_fh

	if pref.has_key('debug_log_file') and pref['debug_log_file']:
		# Open the debug log file, in append mode
		debug_log_fh = open(pref['debug_log_file'],'a')
		debug_log_fh.write("Debug Log Opened at %s\n" % time.strftime('%H:%M:%S, %Y-%m-%d', time.localtime(time.time())))
	else:
		# Set the file handle to False
		debug_log_fh = ''

def close_debug_log():
	global debug_log_fh
	if debug_log_fh:
		debug_log_fh.write("Debug Log Closed at %s\n" % time.strftime('%H:%M:%S, %Y-%m-%d', time.localtime(time.time())))
		debug_log_fh.close()
		debug_log_fh = ''

def init_stumblestore_gsm_log():
	"""Initialise the stumblestore GSM log file"""
	global gsm_log_fh
	gsm_log_fh = open("E:\\gps.log",'a')
def close_stumblestore_gsm_log():
	global gsm_log_fh
	if gsm_log_fh:
		gsm_log_fh.close()
		gsm_log_fh = ''

#############################################################################

def debug_log(rawdata):
	"""Log debug data to a file when requested (if enabled)"""
	global debug_log_fh

	if debug_log_fh:
		debug_log_fh.write(rawdata+"\n")

def gsm_stumblestore_log():
	"""Log the GSM location + GPS location to the stumblestore log file"""
	global location
	global gsm_log_fh

	# Ensure we have our log file open
	if not gsm_log_fh:
		init_stumblestore_gsm_log()

	# Grab the details of what cell we're on
	cell = gsm_location()

	# Write this out
	gsm_log_fh.write("%s,%s,%s,%s,%s,%s,%s,%s\n"%(cell[0],cell[1],cell[2],cell[3],sysinfo.signal(),location['lat_dec'],location['long_dec'],time.time()))

# Kick of logging, if required
init_debug_log()

######################### Log data internally ###############################
def compute_positional_data():
	"""returns 1 if a redraw is needed, otherwise 0"""
	global info
	global waypoints
	global current_waypoint
	global place_of_last_audio_alert
	global log_track

	if (location['valid'] == 0): return 1 # location was invalid, we have to update the screen

	try: del info['last_distance_valid']
	except KeyError: pass

	if current_waypoint != None:
		waypoint = waypoints[current_waypoint]
		# Ensure we're dealing with floats
		try:
			direction_of_lat  = float(waypoint[1])
			direction_of_long = float(waypoint[2])
		except ValueError:
			direction_of_lat  = None
			direction_of_long = None
	else:
		direction_of_lat  = None
		direction_of_long = None

	wgs_ll = get_latlong_floats();
	if wgs_ll != None and direction_of_lat and direction_of_long:

		try:
			res = calculate_distance_and_bearing(wgs_ll[0], wgs_ll[1], direction_of_lat, direction_of_long)
			info['last_distance_valid'] = True
		except:
			res = None
			if info.has_key('last_distance_valid') : del info['last_distance_valid']


		info['dist'], angle = dist_tupel_to_floats(res)
		info['distance_human'] = format_distance(res[0]) # save the distance

		if angle != None:
			if angle < 0: angle = angle + 360
			info['bearing'] = angle
		else:
			if info.has_key('bearing') : del info['bearing']

		# position average
		info['last_avg_position'] = ( info['position_lat_avg'].mean(), info['position_long_avg'].mean())
		info['position_lat_avg'].append(wgs_ll[0])
		info['position_long_avg'].append(wgs_ll[1])
		info['avg_position'] = ( info['position_lat_avg'].mean(), info['position_long_avg'].mean())

		# initialize audio alert place with the first point
		if place_of_last_audio_alert == None: place_of_last_audio_alert = info['avg_position']

		def do_log(pos):
			if not info.has_key('last_log_time'): info['last_log_time'] = time.time()
			if time.time() - info['last_log_time'] > float(log_interval):
				if userpref['log_simple']:
					log_track.log([time.strftime("%d.%m.%Y_%H:%M:%S", time.localtime()), pos[0], pos[1]])
				else:
					save_gga_log()
				info['last_log_time'] = time.time()

		if not info.has_key('d_last_position'):
			info['d_last_position'] = info['avg_position']
			do_log(info['avg_position'])
		else: # do things we want to do when position has changed enough
			try :	res = calculate_distance_and_bearing(info['d_last_position'][0], info['d_last_position'][1], wgs_ll[0], wgs_ll[1])
			except : res = None

			dist, dir = dist_tupel_to_floats(res)
			if dist > 2. * userpref['minimum_warning_distance']:
				info['d_distance'] = dist
				info['d_heading']  = dir
				info['d_last_position'] = info['avg_position']
				if info['d_heading'] != None and info['bearing'] != None:
					info['proposed_direction'] = info['d_heading'] - info['bearing']
					if info['proposed_direction'] < 0. : info['proposed_direction'] += 360

				do_log(info['avg_position'])# log the track to a file

	# moving average of speed
	if motion.has_key('speed') :
		info['speed_mps'] = motion['speed']
		info['speed_avg'].append(motion['speed'])
	else:
		info['speed_avg'].append(0.)

	if motion.has_key('true_heading') and info['speed_avg'].mean() > userpref['minimum_speed_mps']:
		info['avg_heading']  =  float(motion['true_heading'])
	elif motion.has_key('true_heading') and info.has_key('d_heading'):
		act_heading = float(motion['true_heading'])
		info['avg_heading']  = 1./6. *( 5. * info['d_heading'] + act_heading)
	elif not motion.has_key('true_heading') and info.has_key('d_heading'):
		info['avg_heading'] = info['d_heading']
	else:
		try: del info['avg_heading']
		except: pass


	return 1 # redraw by default
#############################################################################

# Lock, so python won't exit during non canvas graphical stuff
lock = e32.Ao_lock()

def exit_key_pressed():
	"""Function called when the user requests exit"""
	global going
	going = 0
	appuifw.app.exit_key_handler = None
	lock.signal()

def callback(event):
	global log_interval
	global current_waypoint
	global waypoints
	global current_state
	global all_photo_sizes
	global photo_size
	global taking_photo
	global pref
	global userpref

	# If they're on the main page, handle changing logging frequency
	if current_state == 'main' or current_state == 'details':
		if event['type'] == appuifw.EEventKeyDown:
			## * -> more frequently
			#if event['scancode'] == 42:
				#if log_interval > 0:
					#log_interval -= 1;
			## # -> less frequently
			#if event['scancode'] == 127:
				#if log_interval > 0:
					#log_interval += 1;
			## 0 -> log a point right now
			#if event['scancode'] == 48:
				#gga_log_count = log_interval
			## 8 -> toggle on/off
			#if event['scancode'] == 56:
				#if log_interval > 0:
					#log_interval = 0;
				#else:
					#log_interval = 10;
					#gga_log_count = 0;
			## 5 -> toggle stumblestore on/off
			#if event['scancode'] == 53:
				#if pref['gsmloc_logging']:
					#pref['gsmloc_logging'] = 0
				#else:
					#pref['gsmloc_logging'] = 1
			# 2 -> toggle kmph / mph
			if event['scancode'] == 50:
				userpref['imperial_speeds'] = not userpref['imperial_speeds']
	if current_state == 'direction_of':
		if event['type'] == appuifw.EEventKeyUp:
			# 1 - prev waypoint
			if event['scancode'] == 49:
				current_waypoint = current_waypoint - 1
				if current_waypoint < 0:
					current_waypoint = len(waypoints) - 1
			# 3 - next waypoint
			if event['scancode'] == 51:
				current_waypoint = current_waypoint + 1
				if current_waypoint >= len(waypoints):
					current_waypoint = 0
			# 5 - make this a waypoint
			if event['scancode'] == 53:
				do_add_as_waypoint()
				# No redraw just yet
				return
			# 8 - remove this waypoint
			if event['scancode'] == 56:
				delete_current_waypoint()
	if current_state == 'take_photo':
		if event['type'] == appuifw.EEventKeyUp:
			size_index = 0
			for i in range(len(all_photo_sizes)):
				if photo_size == all_photo_sizes[i]:
					size_index = i

			# 1 - prev resolution
			if event['scancode'] == 49:
				size_index = size_index - 1
				if size_index < 0:
					size_index = len(all_photo_sizes) - 1
				photo_size = all_photo_sizes[size_index]
			# 3 - next resolution
			if event['scancode'] == 51:
				size_index = size_index + 1
				if size_index >= len(all_photo_sizes):
					size_index = 0
				photo_size = all_photo_sizes[size_index]
			# 0 or enter - take photo
			if event['scancode'] == 48 or event['scancode'] == 167:
				# Request the main thread take it
				# (Takes too long to occur in the event thread)
				taking_photo = 2

	# Whatever happens request a re-draw
	draw_state()

def do_nothing(picked):
	"""Does nothing"""

def main_touch_down_cb(pos=(0,0)):
	global touch
	if not touch.has_key('main_down'):
		touch['drag_start'] = pos
	touch['main_down'] = pos

def main_touch_up_cb(pos=(0,0)):
	global touch
	if touch.has_key('main_down'):
		del touch['main_down']
	if touch.has_key('drag_start'):
		del touch['drag_start']

def drag_callback(pos=(0,0)):
	global touch
	global current_state
	min_width = (3 * screen_width/4.)
	if touch.has_key('drag_start'):
		if not touch.has_key('last_active_drag'): touch['last_active_drag'] = time.time()
		drag_width = abs(pos[0] - touch['drag_start'][0])
		if drag_width > min_width and touch['drag_start'][0] < min_width\
			and time.time() - touch['last_active_drag'] > 0.5:# drag from left to right
			if current_state == 'main': pick_direction_of()
			elif current_state == 'direction_of': pick_track()
			elif current_state == 'track':   pick_os_data()
			elif current_state == 'details': pick_main()
			elif current_state == 'os_data': pick_details()

			touch['last_active_drag'] = time.time()
		elif drag_width > min_width\
			and touch['drag_start'][0] > min_width\
			and time.time() - touch['last_active_drag'] > 0.5:# drag from right to left
			if current_state == 'main': pick_details()
			elif current_state == 'details': pick_os_data()
			elif current_state == 'os_data': pick_track()
			elif current_state == 'track':   pick_direction_of()
			elif current_state == 'direction_of':   pick_main()

			touch['last_active_drag'] = time.time()

def register_drag_mode(canvas):
	canvas.bind(key_codes.EButton1Down, main_touch_down_cb)
	canvas.bind(key_codes.EButton1Up, main_touch_up_cb)
	canvas.bind(key_codes.EDrag, drag_callback)

def touched_on_button(pos, button):
	if  pos[0] >= button[0][0] and pos[0] <  button[1][0]\
	and pos[1] >= button[0][1] and pos[1] <  button[1][1]:
		return True

	return False

def touch_down_main_cb(pos=(0, 0)):
	global touch
	global audio_info_on

	if touched_on_button(pos, touch['buttons'][0]) :
		touch['main_down'] = 'destination'
	elif touched_on_button(pos, touch['buttons'][1]) :
		touch['main_down'] = 'pen'
	elif touched_on_button(pos, touch['buttons'][2]):
		if audio_info_on:
			touch['main_down'] = 'sound'
		else:
			touch['main_down'] = 'sound_off'
	elif touched_on_button(pos, touch['buttons'][3]) :
		touch['main_down'] = 'locked'

def touch_up_main_cb(pos=(0, 0)):
	global touch
	global current_state
	global audio_info_on

	if touch.has_key('main_down'):
		if touch['main_down'] == 'destination':
			current_state = 'destination'
			draw_state()
		elif touch['main_down'] == 'pen':
			current_state = 'logactions'
			draw_state()
			#appuifw.note(u"Log file options not implemented yet", "info")
		elif touch['main_down'] == 'locked':
			pass
		elif touch['main_down'].startswith('sound'):
			audio_info_on = not audio_info_on

		del touch['main_down']

def draw_main():
	global location
	global motion
	global satellites
	global gps
	global log_interval
	global disp_notices
	global disp_notices_count
	global touch, current_state

	#canvas.clear()
	register_drag_mode(canvas)

	myscreen = Image.new((screen_width,screen_height))

	# Draw the top box
	top_box_right = screen_width-10
	top_box_bottom = (line_spacing*2) + 4
	rect0 = ( (10,2),(top_box_right,top_box_bottom))
	myscreen.rectangle(rect0,outline=0x000000, width=1)

	br = screen_height - 45
	lock_pos = screen_width - 45
	wd = 5

	if not touch.has_key('state') or touch['state'] != current_state: # create list of buttons new
		but = []
		but.append( (( wd  ,br), (wd + 40, br + 40 )) )
		but.append( (( wd + 1 * (wd + 40) ,br), (wd + 1 * (wd + 40) + 40, br + 40 )) )
		but.append( (( lock_pos - 45 ,br), (lock_pos -5, br + 40 )) )
		but.append( (( lock_pos ,br), (lock_pos + 40, br + 40 )) )


		if touch.has_key('buttons'): del touch['buttons'][:]
		touch['state'] = current_state
		touch['buttons'] = but

	for i in range(len(touch['buttons'])):
		myscreen.rectangle(touch['buttons'][i],outline=0x000000, width=2)

	def blit_button(name, xpos):
		if touch.has_key('main_down') and touch['main_down'] == name:
			name += '_down'

		if buttons[name]:
			myscreen.blit(buttons[name], target = xpos ) #, scale = 2)

	blit_button('destination', 	touch['buttons'][0][0])
	blit_button('pen', 			touch['buttons'][1][0])
	if audio_info_on: snd = 'sound'
	else: snd = 'sound_off'
	blit_button(snd, 			touch['buttons'][2][0])
	blit_button('locked', 		touch['buttons'][3][0])

	# Draw the two boxes below
	mid = int(screen_width/2)
	left_box_top = (line_spacing*3)
	left_box_bottom = (line_spacing*11)
	right_box_top = (line_spacing*6)
	right_box_bottom = (line_spacing*11)
	right_box_right = screen_width-10

	rect1 = ( (10,left_box_top)     , (mid-10,left_box_bottom) )
	rect2 = ( (mid+10,right_box_top), (right_box_right,right_box_bottom) )
	myscreen.rectangle(rect1,outline=0x000000, width=1)
	myscreen.rectangle(rect2,outline=0x000000, width=1)

	# Draw the heading circle
	heading_centre_r = int(screen_width/4.0*3.0)
	heading_centre_t = int(line_spacing*4.25)
	heading_radius = int(line_spacing*1.5)
	myscreen.ellipse([heading_centre_r-heading_radius,heading_centre_t-heading_radius,heading_centre_r+heading_radius,heading_centre_t+heading_radius], outline=0x000000, width=1)

	# If we're connected, show the location at the top
	# Otherwise, show waiting
	yPos = line_spacing - 6

	indent_box 		= 1 * indent_slight
	indent_box_2 	= 6 * indent_slight
	if gps.connected:

		if (location['valid'] == 0) or (not location.has_key('lat')) or (not location.has_key('long')):
			myscreen.text( (indent_box, yPos), u'(invalid location)', 0x008000, bigger_font )
		else:
			myscreen.text( (indent_box, yPos), u'Latitude', 0x008000, font="normal" )
			myscreen.text( (indent_box, yPos+line_spacing),	u'Longitude', 0x008000, font="normal" )

			myscreen.text( (indent_box_2, yPos), unicode(location['lat']), font="normal" )
			myscreen.text( (indent_box_2, yPos+line_spacing),	unicode(location['long']), font="normal" )

	else:
		myscreen.text( (indent_box,yPos), u"-waiting for gps-", 0xdd0000, font)
		myscreen.text( (indent_box,yPos+line_spacing), unicode(str(gps)), 0xdd0000, font)

	# Heading circle
	#if motion.has_key('true_heading'):
	if (location['valid'] == 1) and info.has_key('distance_human') and info.has_key('bearing'):
			try: angle = float(info['bearing'])
			except: angle = 0.

			centre = (heading_centre_r, heading_centre_t)
			direction = calc_line(heading_radius, angle, centre)

			arrow_l = calc_line(heading_radius-10, angle + 8, centre)
			arrow_r = calc_line(heading_radius-10, angle - 8, centre)
			arrow_l = (direction[0], direction[1], arrow_l[0], arrow_l[1] )
			arrow_r = (direction[0], direction[1], arrow_r[0], arrow_r[1] )


			myscreen.line( direction, outline=0x008000, width=2)
			myscreen.line( arrow_l, outline=0x008000, width=2)
			myscreen.line( arrow_r, outline=0x008000, width=2)

			myscreen.text( (heading_centre_r - 30 ,heading_centre_t-small_line_spacing) , u'%s' % info['distance_human'], 0x008000, font)
			myscreen.text( (heading_centre_r ,heading_centre_t - heading_radius) , u'N' , 0x008000, font)
	else:
		myscreen.text( (heading_centre_r,heading_centre_t), u'?', 0x008000, font)

	# Left box:
	#	time, date, sats, used, logging
	yPos = left_box_top + line_spacing + 4
	if not location.has_key('time'):
		cur_time = u'(no time)'
	else:
		cur_time = location['time']
		if cur_time[-4:] == ' UTC':
			cur_time = cur_time[:-4]
	myscreen.text( (13,yPos), unicode(cur_time), font=font )

	yPos += line_spacing
	if not location.has_key('date'):
		cur_date = u'(no date)'
	else:
		cur_date = location['date']
	myscreen.text( (13,yPos), unicode(cur_date), font=font )

	yPos += int(line_spacing*0.5)
	sPos = mid - 1.5 * line_spacing

	yPos += line_spacing
	myscreen.text( (13, yPos), u'Sats', 0x008000, font)
	if satellites.has_key('in_view'):
		sat_text = len(satellites['in_view'])
	else:
		sat_text = '(u)'
	myscreen.text( (sPos, yPos), unicode(sat_text), font=font )

	yPos += line_spacing
	myscreen.text( (13, yPos), u'Used', 0x008000, font)
	if satellites.has_key('in_use'):
		sat_text = len(satellites['in_use'])
	else:
		sat_text = '(u)'
	myscreen.text( (sPos, yPos), unicode(sat_text), font=font )

	yPos += int(line_spacing*0.5)

	yPos += line_spacing
	if log_interval > 0:
		myscreen.text( (13, yPos), u'Logging', 0x008000, font)

		yPos += line_spacing
		logging = unicode(log_interval) + u' secs'
		if pref['gsmloc_logging']:
			logging = logging + u' +GSM'
		myscreen.text( (13,yPos), logging, font=font)
	else:
		myscreen.text( (13, yPos), u'No Logging', 0x008000, font)

	# Right box:
	#   speed, heading, altitude?
	yPos = right_box_top + line_spacing + 4
	myscreen.text( (mid+13,yPos), u'Speed', 0x008000, font)
	if motion.has_key('speed_mph'):
		if userpref['imperial_speeds']:
			cur_speed = "%0.1f mph" % motion['speed_mph']
		else:
			cur_speed = "%0.1f kmph" % motion['speed_kmph']
		cur_speed = unicode(cur_speed)
	else:
		cur_speed = u'(no speed)'
	yPos += small_line_spacing
	myscreen.text( (mid+13,yPos), cur_speed, font=font)

	if info.has_key('speed_avg') and info['speed_avg'].items > 0:
		cur_speed2 = u"avg : %0.1f kmph" % (info['speed_avg'].mean() * 3.6 )
	else:
		cur_speed2 = u'avg : (no speed)'
	myscreen.text( (mid+13,yPos+small_line_spacing), cur_speed2, font=font)

	yPos += 1.5 * line_spacing
	myscreen.text( (mid+13,yPos), u'Heading', 0x008000, font)
	if motion.has_key('true_heading'):
		mag = "%s deg" % motion['true_heading']
		mag = unicode(mag)
	else:
		mag = u'(no heading)'
	yPos += line_spacing
	myscreen.text( (mid+13,yPos), mag, font=font)

	if info.has_key('avg_heading') and info['avg_heading'] != None:
		myscreen.text( (mid+13,yPos+ small_line_spacing), u'%3d' % int(info['avg_heading']), font=font)
	else:
		myscreen.text( (mid+13,yPos+ small_line_spacing), u'(no heading)', font=font)

	if not disp_notices == '':
		yPos = left_box_bottom + line_spacing
		myscreen.text( (0,yPos), unicode(disp_notices), 0x000080, font)
		disp_notices_count = disp_notices_count + 1
		if disp_notices_count > 60:
			disp_notices = ''
			disp_notices_count = 0
	canvas.blit(myscreen) # show the image on the screen

	# bind the tapping areas
	for i in range(len(touch['buttons'])):
		canvas.bind(key_codes.EButton1Down, touch_down_main_cb, touch['buttons'][i] )
		canvas.bind(key_codes.EButton1Up, touch_up_main_cb, touch['buttons'][i] )

def draw_details():
	global location
	global motion
	global satellites
	global gps
	global log_interval
	global disp_notices
	global disp_notices_count

	canvas.clear()
	register_drag_mode(canvas)
	yPos = line_spacing

	canvas.text( (0,yPos), u'GPS', 0x008000, font)
	if gps.connected:
		canvas.text( (indent_data,yPos), unicode(str(gps)), font=font)
	else:
		indent = int(indent_data/2)
		canvas.text( (indent,yPos), u"-waiting-"+unicode(str(gps)), 0xdd0000, font)

	yPos += line_spacing
	canvas.text( (0,yPos), u'Time:', 0x008000, font)
	if not location.has_key('time'):
		cur_time = u'(unavailable)'
	else:
		cur_time = unicode(location['time'])
	canvas.text( (indent_data,yPos), cur_time, font=font)

	yPos += line_spacing
	canvas.text( (0,yPos), u'Speed', 0x008000, font)
	if motion.has_key('speed_mph'):
		if userpref['imperial_speeds']:
			cur_speed = "%0.1f mph" % motion['speed_mph']
		else:
			cur_speed = "%0.1f kmph" % motion['speed_kmph']
		cur_speed = unicode(cur_speed)
	else:
		cur_speed = u'(unavailable)'
	canvas.text( (indent_data,yPos), cur_speed, font=font)

	yPos += line_spacing
	canvas.text( (0,yPos), u'Heading', 0x008000, font)
	if motion.has_key('true_heading'):
		if motion.has_key('mag_heading') and motion['mag_heading']:
			mag = 'True: ' + motion['true_heading']
			mag = mag + '	Mag: ' + motion['mag_heading']
		else:
			mag = "%s deg" % motion['true_heading']
		mag = unicode(mag)
	else:
		mag = u'(unavailable)'
	canvas.text( (indent_data,yPos), mag, font=font)

	yPos += line_spacing
	canvas.text( (0,yPos), u'Location', 0x008000, font)
	if location.has_key('alt'):
		canvas.text( (indent_large,yPos), unicode(location['alt']), font=font )
	if (not location.has_key('lat')) or (not location.has_key('long')):
		cur_loc = u'(unavailable)'
	else:
		if location['valid'] == 0:
			cur_loc = u'(invalid location)'
		else:
			cur_loc = unicode(location['lat']) + '  ' + unicode(location['long'])
	canvas.text( (indent_slight,yPos+line_spacing), cur_loc, font=font)

	yPos += (line_spacing*2)
	canvas.text( (0, yPos), u'Satellites in view', 0x008000, font)
	if satellites.has_key('in_view'):
		canvas.text( (indent_large,yPos), unicode( len(satellites['in_view']) ), font=font )
		canvas.text( (indent_slight,yPos+line_spacing), unicode(' '.join(satellites['in_view'])), font=font )
	else:
		canvas.text( (indent_slight,yPos+line_spacing), u'(unavailable)', font=font)

	#print satellites
	yPos += (line_spacing*2)
	canvas.text( (0, yPos), u'Satellites used', 0x008000, font)
	if satellites.has_key('in_use'):
		used = len(satellites['in_use'])
		if satellites.has_key('overall_dop'):
			used = str(used) + "  err " + satellites['overall_dop']
		canvas.text( (indent_large,yPos), unicode(used), font=font )
		canvas.text( (indent_slight,yPos+line_spacing), unicode(' '.join(satellites['in_use'])), font=font )
	else:
		canvas.text( (indent_slight,yPos+line_spacing), u'(unavailable)', font=font )

	yPos += (line_spacing*2)
	canvas.text( (0, yPos), u'Logging locations', 0x008000, font)
	if log_interval > 0:
		logging = unicode(log_interval) + u' secs'
	else:
		logging = u'no'
	if pref['gsmloc_logging']:
		logging = logging + u'  +GSM'
	canvas.text( (indent_large,yPos), logging, font=font)

	if not disp_notices == '':
		yPos += line_spacing
		canvas.text( (0,yPos), unicode(disp_notices), 0x000080, font)
		disp_notices_count = disp_notices_count + 1
		if disp_notices_count > 60:
			disp_notices = ''
			disp_notices_count = 0

def touch_down_track_cb(pos=(0, 0)):
	"detect which button was pressed"
	global touch
	if touch.has_key('buttons'):
		for i in range(len(touch['buttons'])):
			if touched_on_button(pos, touch['buttons'][i]):
				touch['down'] = i
				break

def touch_up_track_cb(pos=(0, 0)):
	global touch
	global current_waypoint, waypoints
	global track_xy, waypoints_xy

	if touch.has_key('down'):
		if touch['down'] == 0:
			select_closest_waypoint()
		elif touch['down'] == 1:
			select_prev_waypoint()
			#if current_waypoint > 0: current_waypoint -= 1
		elif touch['down'] == 2:
			select_next_waypoint()
		elif touch['down'] == 3:
			waypoints.reverse()
			old = current_waypoint
			diff = len(waypoints) - 1 - current_waypoint
			current_waypoint = diff
			del waypoints_xy # clear all waypoints
			waypoints_xy = None # they will be computed new
			appuifw.note(u"current_waypoint : %d () old: %d" % (current_waypoint, old), "info")
		elif touch['down'] == 4:
			if not track_xy:
				track_xy = Track(from_file = userpref["logfile"])
			else:
				del track_xy
				track_xy = None
		elif touch['down'] == 5:
			if touch.has_key('zoom'):
				touch['zoom'] *= 2.
			else:
				touch['zoom'] = 2.
		elif touch['down'] == 6:
			if touch.has_key('zoom'):
				touch['zoom'] /= 2.
			else:
				touch['zoom'] = 1.

		del touch['down']
	# delete the last position
	if touch.has_key('last_pos'): del touch['last_pos']

def drag_track_callback(pos=(0,0)):
	global touch
	global current_state
	if not touch.has_key('last_pos'):	touch['last_pos'] = pos
	if not touch.has_key('offset'):		touch['offset'] = [0,0]

	drag = ( (pos[0]-touch['last_pos'][0] ),(pos[1]-touch['last_pos'][1] ))

	canvas.line( (pos,touch['last_pos']), outline=0x0000AA,width=3)

	touch['offset'][0] += drag[0]
	touch['offset'][1] += drag[1]
	touch['last_pos'] = pos

def draw_track():
	global waypoints
	global location
	global current_waypoint
	global touch
	global waypoints_xy
	global track_xy

	wt = screen_width / 3 # wt = width_third
	wd = 5 # window distance to the border

	myscreen = Image.new((screen_width,screen_height))
	mycanvas = None

	if len(waypoints) > 0 :
		mycanvas = ((wd,wd),(screen_width - wd, screen_width - wd))
		myscreen.rectangle(mycanvas,outline=0x000000, width=2)

		if waypoints_xy == None : # compute x,y coordinates and store them in waypoints
			waypoints_xy = Track(waypoints)

		# append current position
		own_position = None
		if location['valid'] == 1:
			wgs_ll = get_latlong_floats()
			try:	own_position = turn_llh_into_xyz(wgs_ll[0],wgs_ll[1],0. ,'wgs84')
			except: own_position = None

		# compute the scaling factor
		if own_position != None:
			xmin = min(waypoints_xy.xrange[0], own_position[0])
			xmax = max(waypoints_xy.xrange[1], own_position[0])

			ymin = min(waypoints_xy.yrange[0], own_position[1])
			ymax = max(waypoints_xy.yrange[1], own_position[1])
		else:
			xmin, xmax = waypoints_xy.xrange
			ymin, ymax = waypoints_xy.yrange

		if track_xy:
			xmin = min(track_xy.xrange[0], xmin)
			xmax = max(track_xy.xrange[1], xmax)

			ymin = min(track_xy.yrange[0], ymin)
			ymax = max(track_xy.yrange[1], ymax)

		xfactor = (xmax - xmin) / float(screen_width - 40)
		yfactor = (ymax - ymin) / float(screen_width - 40)
		factor = max(xfactor, yfactor) # select the largest scaling factor

		if touch.has_key('zoom'):
			factor *= touch['zoom']
			if not touch.has_key('zoom_change') or touch['zoom_change'] != touch['zoom']:
				if touch.has_key('zoom_change') and factor > 0.:
					if touch['zoom'] > touch['zoom_change']:
						touch['offset'][0] =  (touch['offset'][0] + (screen_width)/2.) / 2.
						touch['offset'][1] =  (touch['offset'][1] + (screen_width)/2.) / 2.
					else:
						touch['offset'][0] =  touch['offset'][0]*2. - (screen_width)/2.
						touch['offset'][1] =  touch['offset'][1]*2. - (screen_width)/2.

				touch['zoom_change'] = touch['zoom']
		else:
			touch['zoom'] = 1.

		if not touch.has_key('offset'):
			touch['offset'] = [0,0]

		offset = [0,0]
		offset[0] += touch['offset'][1]
		offset[1] += touch['offset'][0]

		# plot the waypoints
		waypoints_xy.rescale([xmin, ymin], factor, offset)
		for i in range(len(waypoints_xy.coords)-1):
			myscreen.line([waypoints_xy.coords[i][1],waypoints_xy.coords[i][0],waypoints_xy.coords[i+1][1],waypoints_xy.coords[i+1][0]], outline=0x0000AA,width=3)

		# start and end point of the route
		myscreen.point([waypoints_xy.coords[0][1],waypoints_xy.coords[0][0]], outline=0x00AA00, width=10)
		if len(waypoints_xy.coords) > 1:
			l = len(waypoints_xy.coords) -1
			myscreen.point([waypoints_xy.coords[l][1],waypoints_xy.coords[l][0]], outline=0xAA0000, width=10)

		myscreen.point([screen_width/2.,screen_width/2.], outline=0xAA0000, width=10)

		# draw waypoint that is currently approached
		if current_waypoint != None:
			l = current_waypoint
			myscreen.point([waypoints_xy.coords[l][1],waypoints_xy.coords[l][0]], outline=0x007215, width=10)


		#plot the current track
		if track_xy and len(track_xy) > 0:
			track_xy.rescale([xmin, ymin], factor, offset=offset)
			for i in range(len(track_xy.coords)-1):
				myscreen.line([track_xy.coords[i][1],track_xy.coords[i][0],track_xy.coords[i+1][1],track_xy.coords[i+1][0]], outline=0x5B75A5,width=1)

			myscreen.point([track_xy.coords[0][1],track_xy.coords[0][0]], outline=0x00AA00, width=10)
			if len(track_xy) > 1:
				l = len(track_xy.coords) -1
				myscreen.point([track_xy.coords[l][1],track_xy.coords[l][0]], outline=0xAA0000, width=10)

		if own_position:
			xymin = (xmin, ymin)
			for j in [0,1]:
				own_position[j] -= (xymin[j])
				own_position[j] /= factor
				own_position[j] = int(own_position[j]) + offset[j]

			myscreen.point([own_position[1], own_position[0]], outline=0x0000AA, width=10)

		# bind to touch interface
		bh = screen_height - screen_width - 6 # bottom height
		hw = bh/2
		br1 = screen_width +3  # button row 1
		br2 = br1 + 3 + bh/2   # button row 2


		if not touch.has_key('state') or touch['state'] != current_state: # create list of buttons new
			but = []
			for i in range(3): # first button row
				but.append( (( i * wt, br1 ), (	(i+1) * wt , br2-3)) )
			but.append( ( ( 0 * wt, br2 ), ( 1 * wt , screen_height - 3) ) )
			but.append( ( ( 1 * wt, br2 ), ( 3 * wt , screen_height - 3) ) )

			# zoom buttons
			but.append( ( ( screen_width-43, 3 ) , ( screen_width-3 , 43) ) )
			but.append( ( ( screen_width-43, 43 ), ( screen_width-3 , 83) ) )

			if touch.has_key('buttons'): del touch['buttons'][:]
			touch['state'] = current_state
			touch['buttons'] = but

		for i in range(len(touch['buttons'])): # drwa all rectangles
			myscreen.rectangle(touch['buttons'][i],outline=0x000000, width=2)

		but1 = (wt/2 - 20 ,screen_width + 3 + hw/2  - 20)
		if buttons['track_shortest_distance']: # and the images
			myscreen.blit(buttons['track_shortest_distance'], target = but1 ) #, scale = 2)

		# mark as pressed
		if touch.has_key('down'):
			nr = touch['down']
			myscreen.rectangle(touch['buttons'][nr],outline=0x000000, fill=RGB_LIGHT_BLUE, width=2)
			if nr == 0:
				if buttons['track_shortest_distance_down']:
					myscreen.blit(buttons['track_shortest_distance_down'], target = but1) #, scale = 2)

		myscreen.text( (wt + wt/2   , br1 + hw/2-5), u'<', 0x008000, "normal")
		myscreen.text( (2* wt + wt/2, br1 + hw/2-5), u'>', 0x008000, "normal")

		myscreen.text( (3, br2 + hw/2-5), u'<>', 0x008000, "normal")
		if not track_xy:
			myscreen.text( (1.8* wt, br2 + hw/2-5), u'load track', 0x008000, "normal")
		else:
			myscreen.text( (1.8* wt, br2 + hw/2-5), u'unload track', 0x008000, "normal")

		myscreen.text( touch['buttons'][5][0] , u'+', 0x008000, "normal")
		myscreen.text( touch['buttons'][6][0] , u'-', 0x008000, "normal")

		next_direction = get_next_turning_info()
		if next_direction and abs(next_direction) > userpref['min_direction_difference']:
			dir = "right"
			if next_direction < 0.: dir = "left"
			if info.has_key('distance_human'):
				msg = u"in %s %s" % (info['distance_human'], dir)
			else:
				msg = u"next turn : %s" % (dir)
			myscreen.text( ( 2 * wd, screen_width - small_line_spacing), '%s' % (msg), 0x008000, "normal")

	else:
		myscreen.text( ( small_line_spacing, line_spacing), u'No track or destination loaded.' , 0x008000, "normal")

	register_drag_mode(canvas)
	canvas.blit(myscreen) # show the image on the screen
	if mycanvas:
		canvas.bind(key_codes.EButton1Down, touch_down_track_cb, mycanvas)
		canvas.bind(key_codes.EButton1Up, touch_up_track_cb, mycanvas)
		canvas.bind(key_codes.EDrag, drag_track_callback, mycanvas)

	# bind the tapping areas
	if len(waypoints) > 0:
		for i in range(len(touch['buttons'])):
			canvas.bind(key_codes.EButton1Down, touch_down_track_cb,touch['buttons'][i] )
			canvas.bind(key_codes.EButton1Up, touch_up_track_cb, touch['buttons'][i] )



class MapImage:
	def __init__(self, x, y, z, file):
		self.x = x
		self.y = y
		self.z = z
		self.file = file
		self.img = None
		self.loaded = False

def draw_map():
	global Map
	global waypoints
	global location
#	global map_img

	zoomvalue = 11
	if not Map:
		appuifw.note(u'Sorry, but OSM.py not loaded.' ,"error")
		return

	mapinfo = []
	fname = None
	#get the maps
	#for w in waypoints:
		#res = Map.get_map(float(w[1]),float(w[2]),zoomvalue, online = False)
		#if not res in mapinfo: mapinfo.append(MapImage(res[1], res[2], zoomvalue, res[0]))
	mymap = Image.new((screen_width,screen_height))

#	if fname:
#		print fname
#		map_img = Image.open(fname)
#		canvas.blit(map_img,target=(20,20))

#	mymap.blit(map_img,target=(0,0))

	#def turn_llh_into_xyz(lat_dec,long_dec,height,system)

	coords = []
	for w in waypoints:
		#try:
		res = OSM_deg2xy(float(w[1]),float(w[2]),zoomvalue)
		coords.append(res)
		#except:
			#continue

	# append current position
	own_position = None
	if location['valid'] == 1:
		wgs_ll = get_latlong_floats()
		try:	own_position = OSM_deg2xy(wgs_ll[0],wgs_ll[1],zoomvalue) # turn_llh_into_xyz(wgs_ll[0],wgs_ll[1],0. ,'wgs84')
		except: own_position = None

	if len(coords) > 0:
		if own_position:
			xmin = own_position[0]
			xmax = own_position[0]
			ymin = own_position[1]
			ymax = own_position[1]
		else:
			xmin = coords[0][0]
			xmax = coords[0][0]
			ymin = coords[0][1]
			ymax = coords[0][1]

		for i in coords:
			if i[0] < xmin : xmin = i[0]
			if i[0] > xmax : xmax = i[0]
			if i[1] < ymin : ymin = i[1]
			if i[1] > ymax : ymax = i[1]

		#print "----------------------"
		#print xmin, xmax , ymin, ymax

		xfactor = (xmax - xmin) / float(screen_width)
		yfactor = (ymax - ymin) / float(screen_height)
		factor = max(xfactor, yfactor) # select the largest scaling factor

		#print xfactor, yfactor
		if factor:
			for i in range(len(coords)):

				coords[i][0] -= (xmin)
				coords[i][1] -= (ymin)

				coords[i][0] /= factor
				coords[i][1] /= factor

				coords[i][0] = int(coords[i][0])
				coords[i][1] = int(coords[i][1])

			if own_position:
				own_position[0] -= (xmin)
				own_position[1] -= (ymin)

				own_position[0] /= factor
				own_position[1] /= factor

				own_position[0] = int(own_position[0])
				own_position[1] = int(own_position[1])

				canvas.point([own_position[0], own_position[1]], outline=0xAA0000, width=10)

	# plot the track
	for i in range(len(coords)-1):
		mymap.line([coords[i],coords[i+1]], outline=0x0000AA,width=3)

#	canvas.clear()
	canvas.blit(mymap)


def draw_os_data():
	global location

	# We pick up these values as we go
	wgs_height = 0
	wgs_lat = None
	wgs_long = None

	canvas.clear()
	register_drag_mode(canvas)
	if (not location.has_key('lat')) or (not location.has_key('long')):
		canvas.text( (0,line_spacing), u'No location data available', 0x008000, font)
		return

	yPos = line_spacing
	indent_mid = indent_large-indent_slight
	canvas.text( (0,yPos), u'Location (WGS84)', 0x008000, font)
	if location.has_key('alt'):
		canvas.text( (indent_large,yPos), unicode(location['alt']), font=font )

		# Remove ' M'
		wgs_height = location['alt']
		wgs_height = wgs_height[0:-1]
		if wgs_height[-1:] == '':
			wgs_height = wgs_height[0:-1]
	if location['valid'] == 0:
		canvas.text( (indent_slight,yPos+line_spacing), u'(invalid location)', font=font )
	else:
		canvas.text( (indent_slight,yPos+line_spacing), unicode(location['lat']), font=font )
		canvas.text( (indent_mid,yPos+line_spacing), unicode(location['long']), font=font )

		yPos += line_spacing
		canvas.text( (indent_slight,yPos+line_spacing), unicode(location['lat_dec']), font=font )
		canvas.text( (indent_mid,yPos+line_spacing), unicode(location['long_dec']), font=font )

		# remove N/S E/W
		wgs_ll = get_latlong_floats()
		if wgs_ll != None:
			wgs_lat = wgs_ll[0]
			wgs_long = wgs_ll[1]
		else:
			wgs_lat = None
			wgs_long = None

	# Convert these values from WGS 84 into OSGB 36
	osgb_data = []
	if (not wgs_lat == None) and (not wgs_long == None):
		osgb_data = turn_wgs84_into_osgb36(wgs_lat,wgs_long,wgs_height)
	# And display
	yPos += (line_spacing*2)
	canvas.text( (0,yPos), u'Location (OSGB 36)', 0x008000, font)
	if osgb_data == []:
		canvas.text( (indent_slight,yPos+line_spacing), u'(invalid location)', font=font )
	else:
		osgb_lat = "%02.06f" % osgb_data[0]
		osgb_long = "%02.06f" % osgb_data[1]
		canvas.text( (indent_slight,yPos+line_spacing), unicode(osgb_lat), font=font )
		canvas.text( (indent_mid,yPos+line_spacing), unicode(osgb_long), font=font )

	# And from OSG36 into easting and northing values
	en = []
	if not osgb_data == []:
		en = turn_osgb36_into_eastingnorthing(osgb_data[0],osgb_data[1])
	# And display
	yPos += (line_spacing*2)
	canvas.text( (0,yPos), u'OS Easting and Northing', 0x008000, font)
	if en == []:
		canvas.text( (indent_slight,yPos+line_spacing), u'(invalid location)', font=font )
	else:
		canvas.text( (indent_slight,yPos+line_spacing), unicode('E ' + str(int(en[0]))), font=font )
		canvas.text( (indent_mid,yPos+line_spacing), unicode('N ' + str(int(en[1]))), font=font )

	# Now do 6 figure grid ref
	yPos += (line_spacing*2)
	canvas.text( (0,yPos), u'OS 6 Figure Grid Ref', 0x008000, font)
	if en == []:
		canvas.text( (indent_slight,yPos+line_spacing), u'(invalid location)', font=font )
	else:
		six_fig = turn_easting_northing_into_six_fig(en[0],en[1])
		canvas.text( (indent_slight,yPos+line_spacing), unicode(six_fig), font=font )

	# Print the speed in kmph and mph
	yPos += (line_spacing*2)
	canvas.text( (0,yPos), u'Speed', 0x008000, font)
	done_speed = 0
	if motion.has_key('speed_mph'):
		mph_speed = "%0.2f mph" % motion['speed_mph']
		kmph_speed = "%0.2f kmph" % motion['speed_kmph']

		canvas.text( (indent_slight,yPos+line_spacing), unicode(mph_speed), font=font)
		canvas.text( (indent_mid,yPos+line_spacing), unicode(kmph_speed), font=font)
		done_speed = 1
	if done_speed == 0:
		cur_speed = u'(unavailable)'
		canvas.text( (indent_slight,yPos+line_spacing), u'(unavailable)', font=font)

def draw_direction_of():
	global current_waypoint
	global new_waypoints
	global waypoints
	global location
	global motion
	global pref

	yPos = line_spacing
	#canvas.clear()
	myscreen = Image.new((screen_width,screen_height))
	register_drag_mode(canvas)

	if len(waypoints) == 0 or current_waypoint == None:
		myscreen.text( (0,yPos), u'No waypoints available', 0x008000, font)
		return
	else:
		myscreen.text( (0,yPos) , u'waypoint : %d/%d' % (current_waypoint+1, len(waypoints)), 0x008000, font)

	# Grab the waypoint of interest
	waypoint = waypoints[current_waypoint]

	# Ensure we're dealing with floats
	try:
		direction_of_lat  = float(waypoint[1])
		direction_of_long = float(waypoint[2])
	except ValueError:
		appuifw.note(u'ValueError: waypoints lat or long value is not float',"error")
		return

	# Display
	yPos += line_spacing
	indent_mid = int(screen_width * 0.5) # mid of the screen
	# Where are we?
	myscreen.text( (0,yPos), u'Location (WGS84)', 0x008000, font)
	yPos += line_spacing
	if location['valid'] == 0:
		myscreen.text( (indent_slight,yPos), u'(invalid location)', font=font )
	else:
		myscreen.text( (indent_slight,yPos), unicode(location['lat_dec']), font=font )
		myscreen.text( (indent_mid   ,yPos), unicode(location['long_dec']), font=font )

	if info.has_key('last_distance_valid'):

		dist_bearing = (info['dist'], info['bearing'])
		distance = info['distance_human']
		bearing = info['bearing']

		if info.has_key('avg_heading') and info['avg_heading'] != None:
			heading = "%03d" % float(info['avg_heading'])
		else:
			heading = None

		# Where are we going?
		yPos += (line_spacing)
		myscreen.text( (0,yPos), u'Heading to (WGS84) %s' % unicode(waypoint[0]), 0x008000, font)
		heading_lat = "%02.06f" % direction_of_lat
		heading_long = "%02.06f" % direction_of_long
		yPos += (line_spacing)
		myscreen.text( (indent_slight, yPos), unicode(heading_lat), font=font )
		myscreen.text( (indent_mid   , yPos), unicode(heading_long), font=font )

		# Draw our big(ish) circle
		#  radius of 3.75 line spacings, centered on
		#   3.75 line spacings, 8 line spacings
		radius = int(line_spacing*4.25)

		centre = ( int(indent_mid), int(screen_height - radius - 0.25) )
		myscreen.ellipse([centre[0]-radius,centre[1]-radius,centre[0]+radius,centre[1]+radius], outline=0x000000, width=2)
		myscreen.point([centre[0],centre[1]], outline=0x000000, width=1)

		# How far, and what dir?
		yPos += line_spacing
		yPos2 = yPos + small_line_spacing
		third_width = int(screen_width/3.)

		myscreen.text( ( 0 ,yPos), u'Distance', 0x008000, font )
		myscreen.text( ( 0,yPos2), unicode(distance), font=font )
		myscreen.text( ( third_width,yPos), u'Cur Dir', 0x008000, font )
		myscreen.text( ( third_width,yPos2), unicode(heading), font=font )
		myscreen.text( (2*third_width,yPos), u'Head In', 0x008000, font )
		myscreen.text( (2*third_width,yPos2), unicode("%03d" % bearing), 0x800000, font )
		if info.has_key('proposed_direction'):
			myscreen.text( (2*third_width,yPos2+small_line_spacing), unicode("%03d" % info['proposed_direction']), 0x800000, font )

		# What't this waypoint called?
		#yPos = line_spacing*6
		#yPos += 2* line_spacing
		#canvas.text( (indent_mid,yPos), unicode(waypoint[0]), 0x000080, font )
		##canvas.text( (indent_slight,yPos), unicode(waypoint[0]), 0x000080, font )

		# The way we are going is always straight ahead
		# Draw a line + an arrow head
		top = centre[1] - radius
		asize = int(line_spacing/2)
		myscreen.line([centre[0],top,centre[0],centre[1]+radius], outline=0x000000,width=3)
		myscreen.line([centre[0],top,centre[0]+asize,top+asize], outline=0x000000,width=3)
		myscreen.line([centre[0],top,centre[0]-asize,top+asize], outline=0x000000,width=3)

		# use mean value of the last 10 headings
		if info.has_key('avg_heading') :
			true_heading = info['avg_heading']
		else:	# Make sure the true heading is a float
			true_heading = None

		if true_heading:# and info['avg_speed'] >= pref['minimum_speed_mps']: # heading up
			# Draw NS-EW lines, relative to current direction
			ns_coords = calc_line(radius, 0 - true_heading, centre)
			ew_coords = calc_line(radius, 0 - true_heading + 90, centre)

			n_pos = calc_line(radius+4, 0 - true_heading, centre)
			e_pos = calc_line(radius+4, 0 - true_heading + 90, centre)
			s_pos = calc_line(radius+4, 0 - true_heading + 180, centre)
			w_pos = calc_line(radius+4, 0 - true_heading + 270, centre)

			myscreen.line( ns_coords, outline=0x008000, width=2)
			myscreen.line( ew_coords, outline=0x008000, width=2)
			myscreen.text( (n_pos[0]-2,n_pos[1]+4), u'N', 0x008000, font )
			myscreen.text( (s_pos[0]-2,s_pos[1]+4), u'S', 0x008000, font )
			myscreen.text( (e_pos[0]-2,e_pos[1]+4), u'E', 0x008000, font )
			myscreen.text( (w_pos[0]-2,w_pos[1]+4), u'W', 0x008000, font )

			# Draw on the aim-for line
			# Make it relative to the heading
			bearing_coords = calc_line(radius, dist_bearing[1] - true_heading, centre)
			b_a_coords	 = calc_line(radius-asize, dist_bearing[1] - true_heading + 8, centre)
			b_b_coords	 = calc_line(radius-asize, dist_bearing[1] - true_heading - 8, centre)
			b_a = (bearing_coords[0],bearing_coords[1],b_a_coords[0],b_a_coords[1])
			b_b = (bearing_coords[0],bearing_coords[1],b_b_coords[0],b_b_coords[1])

			myscreen.line( bearing_coords, outline=0x800000, width=2)
			myscreen.line( b_a, outline=0x800000, width=2)
			myscreen.line( b_b, outline=0x800000, width=2)
		else: # north up
			# Draw NS-EW lines, relative to current direction
			ns_coords = calc_line(radius, 0., centre)
			ew_coords = calc_line(radius, 90., centre)

			n_pos = calc_line(radius+4, 0 , centre)
			e_pos = calc_line(radius+4, 90., centre)
			s_pos = calc_line(radius+4, 180., centre)
			w_pos = calc_line(radius+4, 270., centre)

			myscreen.line( ns_coords, outline=0x008000, width=2)
			myscreen.line( ew_coords, outline=0x008000, width=2)

			myscreen.text( (n_pos[0]-2,n_pos[1]+4), u'N', 0x008000, bigger_font )
			myscreen.text( (s_pos[0]-2,s_pos[1]+4), u'S', 0x008000, bigger_font )
			myscreen.text( (e_pos[0]-2,e_pos[1]+4), u'E', 0x008000, bigger_font )
			myscreen.text( (w_pos[0]-2,w_pos[1]+4), u'W', 0x008000, bigger_font )

			# Draw on the aim-for line
			# Make it relative to the heading
			bearing_coords = calc_line(radius, dist_bearing[1], centre)
			b_a_coords	 = calc_line(radius-asize, dist_bearing[1] + 8, centre)
			b_b_coords	 = calc_line(radius-asize, dist_bearing[1] - 8, centre)
			b_a = (bearing_coords[0],bearing_coords[1],b_a_coords[0],b_a_coords[1])
			b_b = (bearing_coords[0],bearing_coords[1],b_b_coords[0],b_b_coords[1])

			myscreen.line( bearing_coords, outline=0x800000, width=2)
			myscreen.line( b_a, outline=0x800000, width=2)
			myscreen.line( b_b, outline=0x800000, width=2)

			myscreen.text( (bearing_coords[0]  + 4 ,bearing_coords[1] + 4), unicode(waypoint[0]), 0x000080, font )

			myscreen.text( ( indent_mid - indent_slight, centre[1]), u'No heading !', 0x008000, font )
	else: #direction is unknown
		myscreen.text( (0,yPos + 5 * small_line_spacing), u'No valid position ?', 0x008000, font)
		myscreen.text( (0,yPos + 6 * small_line_spacing), u'wgs_lat / wgs_long not valid', 0x008000, font)
	canvas.blit(myscreen)

def draw_take_photo():
	global location
	global all_photo_sizes
	global photo_size
	global preview_photo
	global photo_displays
	global taking_photo

	canvas.clear()

	# Do we have pexif?
	if not has_pexif:
		yPos = line_spacing
		canvas.text( (0,yPos), u'pexif not found', 0x800000, font)
		yPos += line_spacing
		canvas.text( (0,yPos), u'Please download and install', 0x800000, font)
		yPos += line_spacing
		canvas.text( (0,yPos), u'so photos can be gps tagged', 0x800000, font)
		yPos += line_spacing
		canvas.text( (0,yPos), u'http://benno.id.au/code/pexif/', 0x008000, font)
		return

	# Display current photo resolution and fix
	yPos = line_spacing
	indent_mid = indent_large - indent_slight

	canvas.text( (0,yPos), u'Location (WGS84)', 0x008000, font)
	if location['valid'] == 0:
		canvas.text( (indent_slight,yPos+line_spacing), u'(invalid location)', font=font )
	else:
		canvas.text( (indent_slight,yPos+line_spacing), unicode(location['lat_dec']), font=font )
		canvas.text( (indent_mid,yPos+line_spacing), unicode(location['long_dec']), font=font )
	yPos += (line_spacing*2)

	canvas.text( (0,yPos), u'Resolution', 0x008000, font)
	canvas.text( (indent_mid,yPos), unicode(photo_size), font=font)
	yPos += line_spacing

	# Display a photo periodically
	if (taking_photo == 0) and (photo_displays > 15 or preview_photo == None):
		taking_photo = 1

	# Only increase the count after the photo's taken
	if (taking_photo == 0):
		photo_displays = photo_displays + 1

	# Only display if we actually have a photo to show
	if not preview_photo == None:
		canvas.blit(preview_photo,target=(5,yPos))

def get_file_list(subfolder="logs\\"):
	"Retrieves the list of logfiles stored on the phone"

	if not userpref['base_dir'].endswith('\\'):
		folder = userpref['base_dir'] + '\\'
	else:
		folder = userpref['base_dir']

	folder +=  subfolder
	if not folder.endswith('\\'):
		folder += '\\'
	print folder
	liste = os.listdir(folder)
	ulist = []
	for i in liste:
		if i: ulist.append(unicode(i))
	return ulist

def touch_up_destination_cb(pos=(0, 0)):
	global touch
	global new_destination_form
	global current_waypoint
	global waypoints
	global userpref
	global current_state

	if touch.has_key('down'):
		if touch['down'] == 0:
			new_destination_form.show(clear_all = True)
			current_state = 'main'
		elif touch['down'] == 1: # select a waypoint
			#i=appuifw.multi_selection_list([u"Item1", u"Item2"], style='checkbox', search_field=1)
			list = load_destination_db()
			sel = []
			for i in range(len(list)):
				if list[i][0] != "":
					sel.append(unicode(list[i][0]))
				else:
					sel.append(u"Waypoint %d" % i)
			i=appuifw.selection_list(sel, search_field=1)
			if i > -1:
				waypoints.append(list[i])
				current_waypoint = len(waypoints) - 1 # set the waypoint
			del list
			current_state = 'main'
		elif touch['down'] == 2:
			new_destination_form.show(clear_all = False)
			current_state = 'main'
		elif touch['down'] == 3:

			files = get_file_list(subfolder='logs\\')
			if len(files) > 0:
				i=appuifw.selection_list(files, search_field=1)
				if i > -1:
					if not userpref['base_dir'].endswith('\\'):
						fn = userpref['base_dir'] + '\\logs\\' + files[i]
					else:
						fn = userpref['base_dir'] +'logs\\'+ files[i]
					file = open(fn, "r")
					lines = file.readlines()
					file.close()

					if len(lines) > 0: del waypoints[:]
					for l in lines:
						li = l.strip()
						if li.startswith('#') or len(li) == 0: continue
						wp = li.split()
						waypoints.append(wp)
					appuifw.note(u"# waypoints: %d" % len(waypoints), "info");
					if len(waypoints) > 0:	current_waypoint = 0
					else: current_waypoint = None
					current_state = 'track'
			else:
				appuifw.note(u"No log files found.", "info");
		elif touch['down'] == 4:
			appuifw.note(u"Not implemented yet.", "info");
		elif touch['down'] == 5:
			del waypoints[:]
			current_waypoint = None
			current_state = 'track'

		del touch['down']

def draw_destination():
	global waypoints
	global location
	global current_waypoint
	global touch, current_state

	myscreen = Image.new((screen_width,screen_height))#~

	w = (screen_width - 10) # used width
	wd = 5 # window distance to the border

	if not touch.has_key('state') or touch['state'] != current_state:
		but = []
		but.append( ((wd, wd), (wd + w, wd + 2 * line_spacing)) )
		for i in range(1,6):
			but.append( ((wd, 2 * wd + 2 *i* line_spacing ), (wd + w, wd + ((2*i) + 2) * line_spacing)) )
		try: del touch['buttons'][:]
		except: pass
		touch['buttons'] = but
		touch['state'] = current_state

	for i in range(len(touch['buttons'])):
		myscreen.rectangle(touch['buttons'][i],outline=0x000000, width=2)

	# mark as pressed
	if touch.has_key('down') :
		item = touch['down']
		myscreen.rectangle(touch['buttons'][item],outline=0x000000, fill=RGB_LIGHT_BLUE, width=2)

	myscreen.text( ( touch['buttons'][0][0][0] + wd , touch['buttons'][0][0][1] + line_spacing ) , u'Enter destination ', 0x008000, "normal")
	myscreen.text( ( touch['buttons'][1][0][0] + wd , touch['buttons'][1][0][1] + line_spacing ) , u'Add known destination ', 0x008000, "normal")
	myscreen.text( ( touch['buttons'][2][0][0] + wd , touch['buttons'][2][0][1] + line_spacing ) , u'Add waypoint', 0x008000, "normal")
	myscreen.text( ( touch['buttons'][3][0][0] + wd , touch['buttons'][3][0][1] + line_spacing ) , u'Load track from log', 0x008000, "normal")
	myscreen.text( ( touch['buttons'][4][0][0] + wd , touch['buttons'][4][0][1] + line_spacing ) , u'Load track from gpx', 0x008000, "normal")
	myscreen.text( ( touch['buttons'][5][0][0] + wd , touch['buttons'][5][0][1] + line_spacing ) , u'Clear current track', 0x008000, "normal")

	#register_drag_mode(canvas)
	canvas.blit(myscreen) # show the image on the screen

	# bind the tapping areas
	for i in touch['buttons']:
		canvas.bind(key_codes.EButton1Down, touch_down_track_cb, i )
		canvas.bind(key_codes.EButton1Up, touch_up_destination_cb, i )

def touch_up_logactions_cb(pos=(0, 0)):
	global touch
	global new_destination_form
	global current_waypoint
	global waypoints
	global userpref
	global current_state

	if touch.has_key('down'):
		if touch['down'] == 0:
			pick_new_file()
		elif touch['down'] == 1:
			files = get_file_list(subfolder='logs\\')
			if len(files) > 0:
				i=appuifw.multi_selection_list(files, search_field=1)
				if i > -1:
					for j in i:
						if not userpref['base_dir'].endswith('\\'):
							fn = userpref['base_dir'] + '\\logs\\' + files[j]
						else:
							fn = userpref['base_dir'] +'logs\\'+ files[j]
						os.remove(fn)
						appuifw.note(u"Deleting %s." % fn, "info");
			else:
				appuifw.note(u"No log files found.", "info");
		else:
			appuifw.note(u"Not implemented yet", "info")

		del touch['down']

def draw_log_actions():
	global waypoints
	global location
	global current_waypoint
	global touch, current_state

	myscreen = Image.new((screen_width,screen_height))#~

	w = (screen_width - 10) # used width
	wd = 5 # window distance to the border

	if not touch.has_key('state') or touch['state'] != current_state:
		but = []
		#but.append( ((wd, wd), (wd + w, wd + 2 * line_spacing)) )
		for i in range(3):
			but.append( ((wd, 2 * wd + 2 *i* line_spacing ), (wd + w, wd + ((2*i) + 2) * line_spacing)) )
		try: del touch['buttons'][:]
		except: pass
		touch['buttons'] = but
		touch['state'] = current_state

	for i in range(len(touch['buttons'])):
		myscreen.rectangle(touch['buttons'][i],outline=0x000000, width=2)

	# mark as pressed
	if touch.has_key('down') :
		item = touch['down']
		myscreen.rectangle(touch['buttons'][item],outline=0x000000, fill=RGB_LIGHT_BLUE, width=2)

	myscreen.text( ( touch['buttons'][0][0][0] + wd , touch['buttons'][0][0][1] + line_spacing ) , u'Start new log file', 0x008000, "normal")
	myscreen.text( ( touch['buttons'][1][0][0] + wd , touch['buttons'][1][0][1] + line_spacing ) , u'Delete log files', 0x008000, "normal")
	myscreen.text( ( touch['buttons'][2][0][0] + wd , touch['buttons'][2][0][1] + line_spacing ) , u'Merge log files', 0x008000, "normal")

	#register_drag_mode(canvas)
	canvas.blit(myscreen) # show the image on the screen

	# bind the tapping areas
	for i in touch['buttons']:
		canvas.bind(key_codes.EButton1Down, touch_down_track_cb, i )
		canvas.bind(key_codes.EButton1Up, touch_up_logactions_cb, i )

# Handle config entry selections
config_lb = ""
def config_menu():
	# Do nothing for now
	global config_lb
	global canvas
	appuifw.body = canvas

# Select the right draw state
current_state = 'main'
def draw_state():
	"""Draw the currently selected screen"""
	global current_state
	global waypoints_xy, track_xy

	# if we draw somthing different than the track delete screen
	# coordinates ...they will be computed next time again
	if current_state != 'track':
		try:
			del waypoints_xy
			del track_xy
		except: pass
		waypoints_xy = None
		track_xy = None

	if current_state == 'os_data':
		draw_os_data()
	elif current_state == 'direction_of':
		draw_direction_of()
	elif current_state == 'take_photo' and has_camera:
		draw_take_photo()
	elif current_state == 'details':
		draw_details()
	elif current_state == 'track':
		draw_track()
	elif current_state == 'map':
		draw_map()
	elif current_state == 'destination':
		draw_destination()
	elif current_state == 'logactions':
		draw_log_actions()
	else:
		draw_main()

# Menu selectors
def pick_main():
	global current_state
	current_state = 'main'
	draw_state()
def pick_map():
	global current_state
	current_state = 'map'
	draw_state()
def pick_track():
	global current_state
	current_state = 'track'
	draw_state()
def pick_details():
	global current_state
	current_state = 'details'
	draw_state()
def pick_os_data():
	global current_state
	current_state = 'os_data'
	draw_state()
def pick_direction_of():
	global current_state
	current_state = 'direction_of'
	draw_state()
def pick_take_photo():
	global current_state
	current_state = 'take_photo'
	draw_state()

def pick_config():
	global settings_form
	global userpref
	"""TODO: Make me work!"""
	#global config_lb
	#config_entries = [ u"GPS", u"Default GPS",
		#u"Logging Interval", u"Default Logging" ]
	#config_lb = appuifw.Listbox(config_entries,config_menu)
	#appuifw.body = config_lb
	#appuifw.note(u'Configuration menu not yet supported!\nEdit script header to configure',"info")
	settings_form.show(userpref)

def pick_upload():
	"""TODO: Implement me!"""
	appuifw.note(u'Please use upload_track.py\nSee http://gagravarr.org/code/', "info")
def pick_new_file():
	do_pick_new_file(u"track")
def do_pick_new_file(def_name):
	global pref
	global userpref
	global log_track

	# Get new filename
	new_name = appuifw.query(u"Basename for new file?", "text", def_name)

	if new_name and len(new_name) > 0:
		# Check it doesn't exist
		new_file_name = userpref['base_dir']+'logs\\' + new_name
		if os.path.exists(new_file_name):
			appuifw.note(u"That file already exists", "error")
			do_pick_new_file(new_name) # ask again for new file
			return

		del log_track # close the old log file
		log_track = LogFile(userpref['base_dir']+'logs\\', new_file_name) # open new one
		userpref["logfile"] = log_track.fullpath
		appuifw.note(u"Now logging to new file %s" % os.path.basename(log_track.fullpath))

def do_add_as_waypoint():
	"""Prompt for a name, then add a waypoint for the current location"""
	global location

	name = appuifw.query(u'Waypoint name?', 'text')
	if name:
		wgs_ll = get_latlong_floats();
		lat = wgs_ll[0]
		long = wgs_ll[1]

		add_waypoint(name, lat, long)
		appuifw.note(u'Waypoint Added','info')

#############################################################################

class GPS(object):
	connected = False
	def connect(self):
		"""Try connect to the GPS, and return if it worked or not"""
		return False
	def identify_gps(self):
		"""Figure out what GPS to use, and do any setup for that"""
		pass
	def process(self):
		"""Process any pending GPS info, and return if a screen update is needed or not"""
		return 0
	def shutdown(self):
		"""Do any work required for the shutdown"""
		pass

class BT(GPS):
	def __init__(self):
		self.gps_addr = None
		self.target = None
		self.sock = None
	def __repr__(self):
		return self.gps_addr
	def identify_gps(self):
		"""Decide which Bluetooth GPS to connect to"""
		if not pref['def_gps_addr'] == '':
			self.gps_addr = pref['def_gps_addr']
			self.target=(self.gps_addr,1)
			# Alert them to the GPS we're going to connect
			#  to automatically
			appuifw.note(u"Will connect to GPS %s" % self.gps_addr, 'info')
		else:
			# Prompt them to select a bluetooth GPS
			self.gps_addr,services=socket.bt_discover()
			self.target=(self.gps_addr,services.values()[0])
	def shutdown(self):
		self.sock.close()
		self.connected = False
	def connect(self):
		try:
			# Connect to the bluetooth GPS using the serial service
			self.sock = socket.socket(socket.AF_BT, socket.SOCK_STREAM)
			self.sock.connect(self.target)
			self.connected = True
			debug_log("CONNECTED to GPS: target=%s at %s" % (str(self.target), time.strftime('%H:%M:%S', time.localtime(time.time()))))
			disp_notices = "Connected to GPS."
			appuifw.note(u"Connected to the GPS")
			return True
		except socket.error, inst:
			self.connected = False
			disp_notices = "Connect to GPS failed.  Retrying..."
			#appuifw.note(u"Could not connected to the GPS. Retrying in 5 seconds...")
			#e32.ao_sleep(5)
			return False
	def process(self):
		global log_track
		try:
			rawdata = readline(self.sock)
		except socket.error, inst:
			# GPS has disconnected, bummer
			self.connected = False
			debug_log("DISCONNECTED from GPS: socket.error %s at %s" % (str(inst), time.strftime('%H:%M:%S, %Y-%m-%d', time.localtime(time.time()))))
			location = {}
			location['valid'] = 1
			appuifw.note(u"Disconnected from the GPS. Retrying...")
			return 0

		# Try to process the data from the GPS
		# If it's gibberish, skip that line and move on
		# (Not all bluetooth GPSs are created equal....)
		try:
			data = rawdata.strip()

			# Discard fragmentary sentences -  start with the last '$'
			startsign = rawdata.rfind('$')
			data = data[startsign:]

			# Ensure it starts with $GP
			if not data[0:3] == '$GP':
				return 0

			# If it has a checksum, ensure that's correct
			# (Checksum follows *, and is XOR of everything from
			#  the $ to the *, exclusive)
			if data[-3] == '*':
				exp_checksum = generate_checksum(data[1:-3])
				if not exp_checksum == data[-2:]:
					disp_notices = "Invalid checksum %s, expecting %s" % (data[-2:], exp_checksum)
					return 0

				# Strip the checksum
				data = data[:-3]

			# Grab the parts of the sentence
			talker = data[1:3]
			sentence_id = data[3:6]
			sentence_data = data[7:]

			# Do we need to re-draw the screen?
			redraw = 0

			# The NMEA location sentences we're interested in are:
			#  GGA - Global Positioning System Fix Data
			#  GLL - Geographic Position
			#  RMC - GPS Transit Data
			if sentence_id == 'GGA':
				do_gga_location(sentence_data)
				redraw = 1

				# Log GGA packets periodically
				save_gga_log(rawdata)
			if sentence_id == 'GLL':
				do_gll_location(sentence_data)
				redraw = 1
			if sentence_id == 'RMC':
				do_rmc_location(sentence_data)
				redraw = 1

			# The NMEA satellite sentences we're interested in are:
			#  GSV - Satellites in view
			#  GSA - Satellites used for positioning
			if sentence_id == 'GSV':
				do_gsv_satellite_view(sentence_data)
				redraw = 1
			if sentence_id == 'GSA':
				do_gsa_satellites_used(sentence_data)
				redraw = 1

			# The NMEA motion sentences we're interested in are:
			#  VTG - Track made good
			# (RMC - GPS Transit - only in knots)
			if sentence_id == 'VTG':
				do_vtg_motion(sentence_data)
				redraw = 1

		# Catch exceptions cased by the GPS sending us crud
		except (RuntimeError, TypeError, NameError, ValueError, ArithmeticError, LookupError, AttributeError), inst:
			print "Exception: %s" % str(inst)
			debug_log("EXCEPTION: %s" % str(inst))
			return 0

		return redraw

class PythonPositioning(GPS):
	"S60 Python Positioning module powered GPS Functionality"
	def __init__(self):
		self.id = None
		self.default_id = positioning.default_module()
		self.type = "Unknown"
	def __repr__(self):
		return self.type
	def identify_gps(self):
		modules = positioning.modules()

		# Try for assisted, then internal, then BT, then default
		#for wanted in ("Assisted", "Integrated", "Bluetooth"):
		for wanted in ("Integrated", "Bluetooth"):
			for module in modules:
				if self.id:
					continue
				if not module['available']:
					continue
				if module['name'].startswith(wanted):
					self.id = module['id']

					name = module['name']
					if name.endswith(" GPS"):
						name = name[0:-4]
					self.type = name
					print "Picked %s with ID %d" % (module['name'], self.id)
		# Go with the default if all else fails
		if not self.id:
			self.id = self.default_id
	def connect(self):
		# Connect, and install the callback
		try:
			print "Activating module with id '%d'" % self.id
			positioning.select_module(self.id)
			positioning.set_requestors([{"type":"service",
									"format":"application",
									"data":"nmea_info"}])

			positioning.position(
								course=1,
								satellites=1,
								callback=process_positioning_update,
								interval=1000000,
								partial=1
			)
			self.connected = True
			appuifw.note(u"Connected to the GPS Location Service")
			return True
		except Exception, reason:
			disp_notices = "Connect to GPS failed with %s, retrying" % reason
			self.connected = False
			return False
	def process(self):
		# return value 1: we need a redraw, 0: we need no redraw
		e32.ao_sleep(0.4)
		return 1
	def shutdown(self):
		positioning.stop_position()

if has_positioning and not pref['force_bluetooth']:
	gps = PythonPositioning()
	#appuifw.note(u'"Iternal GPS positioning will be used."',"info")
else:
	gps = BT()
	#appuifw.note(u'"Looking for Bluetooth devices"',"info")
gps.identify_gps()

# Not yet connected
gps.connected = False

#############################################################################

# Enable these displays, now all prompts are over
canvas=appuifw.Canvas(event_callback=callback,
		redraw_callback=lambda rect:draw_state())

# Figure out how big our screen is
# Note - don't use sysinfo.display_pixels(), as we have phone furnature
screen_width,screen_height = canvas.size
if screen_width > (screen_height*1.25):
	appuifw.note(u"This application is optimised for portrait view, some things may look odd", "info")
print "Detected a resolution of %d by %d" % (screen_width,screen_height)

# Decide on font and line spacings. We want ~12 lines/page
line_spacing = int(screen_height/16)
small_line_spacing = int(line_spacing * 0.5)
all_fonts = appuifw.available_fonts()
print all_fonts
font = None
if u'LatinBold%d' % line_spacing in all_fonts:
	font = u'LatinBold%d' % line_spacing
elif u'LatinPlain%d' % line_spacing in all_fonts:
	font = u'LatinPlain%d' % line_spacing
elif u'Series 60 Sans' in all_fonts:
	font = u'Series 60 Sans'
else:
	# Look for one with the right spacing, or close to it
	for f in all_fonts:
		if f.endswith(str(line_spacing)):
			font = f
	if font == None:
		for f in all_fonts:
			if f.endswith(str(line_spacing-1)):
				font = f
	if font == None:
		# Give up and go with the default
		font = "normal"
print "Selected line spacing of %d and the font %s" % (line_spacing,font)
# while converting
#font = u"LatinPlain12"

bigger_font = "normal"


# How far across the screen to draw things in the list views
indent_slight = int(line_spacing * 0.85)   #v2=10
indent_data   = int(line_spacing * 4.0) + 12 #v2=60
indent_large  = int(line_spacing * 8.75)	#v2=105

# Get the sizes for photos
all_photo_sizes = []
preview_size = None
if has_camera:
	all_photo_sizes = camera.image_sizes()
	all_photo_sizes.sort(lambda x,y: cmp(x[0],y[0]))
	photo_size = all_photo_sizes[0]
	for size in all_photo_sizes:
		if size[0] < screen_width and size[1] < screen_height:
			preview_size = size
	if preview_size == None:
		preview_size = all_photo_sizes[0]
	print "Selected a preview photo size of %d by %d" % (preview_size[0],preview_size[1])

#audio.say("Hallo Stefan.")

# Make the canvas active
appuifw.app.body=canvas

# TODO: Make canvas and Listbox co-exist without crashing python
appuifw.app.menu=[
	(u'Main Screen',pick_main),
	(u'Details Screen',pick_details),
	(u'Show track',pick_track),
	(u'Show map',pick_map),
	(u'OS Data',pick_os_data),
	(u'Direction Of',pick_direction_of),
	(u'Take Photo',pick_take_photo),
	(u'Upload',pick_upload),
	(u'Configuration',pick_config),
	]

#############################################################################

# Start the lock, so python won't exit during non canvas graphical stuff
lock = e32.Ao_lock()


# start the timer
info_thread = thread.start_new_thread(speech_timer,())

if not audio_info_on: #userpref['audio_info_on'] :
	appuifw.note(u"audio info is OFF", "info")

if userpref.has_key('logfile'): # load last logfile
	log_track=LogFile(userpref['base_dir']+'logs\\', 'track', fullname = userpref['logfile'])
else:
	log_track=LogFile(userpref['base_dir']+'logs\\', 'track')

# Loop while active
appuifw.app.exit_key_handler = exit_key_pressed
while going > 0:
	# Connect to the GPS, if we're not already connected
	if not gps.connected:
		worked = gps.connect()
		if not worked:
			# Sleep for a tiny bit, then retry
			e32.ao_sleep(0.2)
			continue

	# Take a preview photo, if they asked for one
	# (Need to do it in this thread, otherwise it screws up the display)
	if taking_photo == 1:
		new_photo = camera.take_photo(
							mode='RGB12', size=preview_size,
							flash='none', zoom=0, exposure='auto',
							white_balance='auto', position=0 )
		preview_photo = new_photo
		if taking_photo == 1:
			# In case they requested a photo take while doing the preview
			taking_photo = 0
		photo_displays = 0
	# Take a real photo, and geo-tag it
	# (Need to do it in this thread, otherwise it screws up the display)
	if taking_photo == 2:
		new_photo = camera.take_photo(
								mode='RGB16', size=photo_size,
								flash='none', zoom=0, exposure='auto',
								white_balance='auto', position=0 )
		# Write out
		filename = "E:\\Images\\GPS-%d.jpg" % int(time.time())
		new_photo.save(filename, format='JPEG',
							quality=75, bpp=24, compression='best')
		# Grab the lat and long, and trim to 4dp
		# (Otherwise we'll cause a float overflow in pexif)
		wgs_ll = get_latlong_floats();
		print "Tagging as %s %s" % (wgs_ll[0],wgs_ll[1])
		# Geo Tag it
		geo_photo = JpegFile.fromFile(filename)
		geo_photo.set_geo( wgs_ll[0], wgs_ll[1] )
		geo_photo.writeFile(filename)
		# Done
		appuifw.note(u"Taken photo", 'info')
		taking_photo = 0

	# If we are connected to the GPS, read a line from it
	if gps.connected:
		redraw = gps.process()

		redraw = compute_positional_data()

		# Update the state display if required
		if redraw == 1:
			draw_state()
		#e32.ao_sleep(1) # sleep 1s for redraw

	else:
		# Sleep for a tiny bit before re-trying
		e32.ao_sleep(0.2)

else:
	# All done
	userpref['logfile'] = log_track.fullpath
	write_settings(userpref)
	gps.shutdown()
	close_debug_log()
	close_stumblestore_gsm_log()

print "All done"
#appuifw.app.set_exit()
