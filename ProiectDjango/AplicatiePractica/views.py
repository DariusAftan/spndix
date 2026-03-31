from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Cheltuiala, Categorie
from .forms import CheltuialaForm
from django.contrib import messages


@login_required
def lista_cheltuieli(request):
    cheltuieli = Cheltuiala.objects.filter(utilizator=request.user)
    return render(request, 'AplicatiePractica/lista.html', {'cheltuieli': cheltuieli})


@login_required
def adauga_cheltuiala(request):
    if request.method == 'POST':
        form = CheltuialaForm(request.POST)
        if form.is_valid():
            cheltuiala = form.save(commit=False)
            cheltuiala.utilizator = request.user
            cheltuiala.save()
            messages.success(request, f'Cheltuiala "{cheltuiala.titlu}" a fost adăugată!')
            return redirect('lista_cheltuieli')
    else:
        form = CheltuialaForm()
    return render(request, 'AplicatiePractica/form.html', {'form': form, 'titlu': 'Adaugă Cheltuială'})


@login_required
def editeaza_cheltuiala(request, pk):
    cheltuiala = get_object_or_404(Cheltuiala, pk=pk, utilizator=request.user)
    if request.method == 'POST':
        form = CheltuialaForm(request.POST, instance=cheltuiala)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cheltuiala "{cheltuiala.titlu}" a fost actualizată!')
            return redirect('lista_cheltuieli')
    else:
        form = CheltuialaForm(instance=cheltuiala)
    return render(request, 'AplicatiePractica/form.html', {'form': form, 'titlu': 'Editează Cheltuială'})

@login_required
def sterge_cheltuiala(request, pk):
    cheltuiala = get_object_or_404(Cheltuiala, pk=pk, utilizator=request.user)
    if request.method == 'POST':
        cheltuiala.delete()
        messages.success(request, f'Cheltuiala "{cheltuiala.titlu}" a fost ștearsă!')
        return redirect('lista_cheltuieli')
    return render(request, 'AplicatiePractica/confirmare_stergere.html', {'cheltuiala': cheltuiala})