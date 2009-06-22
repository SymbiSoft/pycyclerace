

# for information see
# http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Zoom_levels

#lat = 52.509810
#lon = 13.325761
#zoom = 12

#basefolder = "."

import math, urllib, os, errno


def OSM_deg2num(lat_deg, lon_deg, zoom):
	lat_rad = lat_deg * math.pi / 180.0
	n = 2.0 ** zoom
	xtile = int((lon_deg + 180.0) / 360.0 * n)
	ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
	return xtile, ytile

def OSM_deg2xy(lat_deg, lon_deg, zoom):
	lat_rad = lat_deg * math.pi / 180.0
	n = 2.0 ** zoom
	#n = 1.
	x = (lon_deg + 180.0) / 360.0 * n
	y = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
	return [x, y]

def OSM_num2deg(xtile, ytile, zoom):
	n = 2.0 ** zoom
	lon_deg = xtile / n * 360.0 - 180.0
	lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
	lat_deg = lat_rad * 180.0 / math.pi
	return lat_deg, lon_deg


class OSM_Loader():
	def __init__(self, url = "http://tile.openstreetmap.org/%d/%d/%d.png", folder='.'):
		self.baseurl = url
		self.folder  = folder

	def get_map(self, lat, lon, zoom = 16, online=True):
		res = OSM_deg2num(lat, lon,zoom)
		url = self.baseurl % (zoom, res[0], res[1])
		folder = os.path.join(self.folder, str(zoom), str(res[0]))
		try:	os.makedirs(folder)
		except OSError, e :					# if path already exists, an exceptions is raised
			if e.errno != errno.EEXIST : raise # if it was another exception, then raise again

		file = os.path.join(folder, str(res[1])) + '.png'
		if not os.path.exists(file):
			urllib.urlretrieve(url, file)

		return file, res[0], res[1] # filename, x, y



