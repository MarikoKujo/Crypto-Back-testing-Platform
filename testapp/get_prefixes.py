import calendar
import datetime

def get_prefixes(start, end=None):
	"""Generate prefixes for searching files in idp_crypto bucket.
	A filename uses a UNIX timestamp as prefix. Thus we are able to 
	list files created during a day.
	Normally start time is 00:20:00 of last day, and end time is 
	00:20:00 of current day, given that collection of yesterday's 
	data should be finished then. 

	IMPORTANT: This method relies on the current format of filename.
	i.e., using UNIX timestamp as prefix for every file. As GCS does 
	not support directly listing all files added in a certain period 
	of time, this function is used as a workaround.
	If filename scheme changes, this method may become invalid.
	If GCS adds API for listing files according to time, this method
	should be replaced with directly accessing the API.
	----------------------------------
	Examples:

	1541031600 2018-11-01 00:20:00 start
	1541118000 2018-11-02 00:20:00 end
	prefixes:
	head1	tail1
	1541031-1541039
	head2	tail2
	154104 -154109
	head3	tail3
	154110 -154111

	1543796400 2018-12-03 00:20:00 start
	1543882800 2018-12-04 00:20:00 end
	prefixes:
	head1	tail1
	1543796-1543799
	head2	tail2
	154380 -154389
	154389 >= 154388 : no head3 && tail3
	----------------------------------

	Parameters:
	start : string, in format of "2018-11-01 00:20:00", UTC
	end : string, 00:20:00 of current day by default, UTC

	Returns:
	prefixes : list, contains strings as prefixes to look up with
	"""
	prefixes = []

	startstamp = calendar.timegm(datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S').timetuple())
	startstamp = int(startstamp)

	if end is None:
		end = datetime.datetime.utcnow().date().strftime('%Y-%m-%d')
		end = end + ' 00:20:00'
	endstamp = calendar.timegm(datetime.datetime.strptime(end, '%Y-%m-%d %H:%M:%S').timetuple())
	endstamp = int(endstamp)

	head1 = startstamp // 1000
	tail1 = (head1 // 10 + 1) * 10 - 1
	if head1 == tail1:
		prefixes.append(str(head1))  # can be omitted, but this may be a little faster
	else:
		prefixes += [str(i) for i in range(head1, tail1+1)]

	head2 = head1 // 10 + 1
	tail2 = (head2 // 10 + 1) * 10 - 1
	if head2 == tail2:
		prefixes.append(str(head2))
	else:
		prefixes += [str(i) for i in range(head2, tail2+1)]

	tail3 = endstamp // 10000
	if tail2 < tail3:
		prefixes += [str(i) for i in range(tail2+1, tail3+1)]

	return prefixes