from django.shortcuts import render

def index(request):
    context = {'message': 'Hello, Django!'}
    return render(request, 'scraper/index.html', context)
