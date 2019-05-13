import calendar
import datetime

def get_prefixes(start, end=None):
	"""Generate prefixes for searching files in idp_crypto bucket.
	A filename uses a UNIX timestamp as prefix. Thus we are able to 
	list files created in a certain period of time.
	Normally start time is 00:26:00 of last day, and end time is set 
	to 00:20:00 of current day, given that collection of yesterday's 
	data should be finished by 00:08:00. 

	Parameters:
	start : string, in format of "2018-11-01 00:26:00"
	end : string, 00:20:00 of current day by default. This param is 
			only used for testing.

	Returns:
	prefixes : list, contains strings as prefixes to look up with
	"""
	prefixes = []
	startstamp = calendar.timegm(datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S').timetuple())
	# startstamp = ('%d' % startstamp)
	startstamp = int(startstamp)
	if end is None:
		end = datetime.datetime.utcnow().date().strftime('%Y-%m-%d')
		end = end + ' 00:20:00'
	endstamp = calendar.timegm(datetime.datetime.strptime(end, '%Y-%m-%d %H:%M:%S').timetuple())
	# endstamp = ('%d' % endstamp)
	endstamp = int(endstamp)

	print(startstamp)
	print(endstamp)

	head1 = startstamp // 1000
	tail1 = (head1 // 10 + 1) * 10 - 1
	if head1 == tail1:
		prefixes.append(str(head1))
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