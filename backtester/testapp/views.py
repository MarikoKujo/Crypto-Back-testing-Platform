from django.shortcuts import render

# Create your views here.
def index(request):
	context = {'assets':['BTCUSDT','ETHBTC','XLMBTC','XRPBTC']}
	return render(request, 'testapp/index.html', context)

def results(request):
	context = {}
	# maybe replace with another template here
	return render(request, 'testapp/index.html', context)