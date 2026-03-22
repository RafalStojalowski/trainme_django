from django.shortcuts import render
from django.http import JsonResponse
import json

def home(request):
    return render(request, 'home/home.html')


def speech_input(request):
    if request.method == "POST":
        data = json.loads(request.body)

        # Tutaj bedzie sie zbierac caly tekst z rozpoznawania mowy ale tylko po zakonczeniu sesji, nie robi sie w czasie rzeczywistym
        text = data.get("text", "")

        print("USER SAID:", text) 

        return JsonResponse({"status": "ok"})