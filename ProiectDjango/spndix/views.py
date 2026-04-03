from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Cheltuiala, Categorie, Budget, AIAnaliza, UserProfile, ForecastAlert, LUNA_CHOICES
from .forms import CheltuialaForm, RegisterForm, BudgetForm, UserProfileForm
from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Sum
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse
import json
import base64
import re
import uuid
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from datetime import date, timedelta
from calendar import monthrange

import PIL.Image
from PIL import ImageOps, UnidentifiedImageError
from pypdf import PdfReader
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import google.generativeai as genai


def construieste_buget_dashboard(buget, utilizator):
    suma_cheltuita = Cheltuiala.objects.filter(
        utilizator=utilizator,
        categorie=buget.categorie,
        data__month=buget.luna,
        data__year=buget.an,
    ).aggregate(total=Sum('suma'))['total'] or 0

    suma_limita = float(buget.suma_limita)
    suma_cheltuita_float = float(suma_cheltuita)
    procent = 0 if suma_limita == 0 else (suma_cheltuita_float / suma_limita) * 100
    progres = min(procent, 100)

    if procent > 100:
        clasa = 'bg-danger'
        status = 'Depășit'
    elif procent >= 80:
        clasa = 'bg-warning text-dark'
        status = 'Aproape de limită'
    else:
        clasa = 'bg-success'
        status = 'În regulă'

    return {
        'id': buget.pk,
        'categorie': buget.categorie,
        'luna': buget.luna,
        'luna_display': buget.get_luna_display(),
        'an': buget.an,
        'suma_limita': suma_limita,
        'suma_cheltuita': suma_cheltuita_float,
        'procent': round(procent, 1),
        'progres': round(progres, 1),
        'bar_class': clasa,
        'status': status,
        'excedat': procent > 100,
        'ramas': round(max(suma_limita - suma_cheltuita_float, 0), 2),
        'depasire': round(max(suma_cheltuita_float - suma_limita, 0), 2),
    }


def rotunjeste_bani(valoare):
    return Decimal(valoare or 0).quantize(Decimal('0.01'))


def creeaza_alerta_daca_nu_exista(
    utilizator,
    categorie,
    tip,
    mesaj,
    suma_implicata,
    zile_ramase,
    actiune_recomandata,
):
    azi = timezone.localdate()
    exista = ForecastAlert.objects.filter(
        utilizator=utilizator,
        categorie=categorie,
        tip=tip,
        mesaj=mesaj,
        creat_la__date=azi,
    ).exists()
    if exista:
        return None

    return ForecastAlert.objects.create(
        utilizator=utilizator,
        categorie=categorie,
        tip=tip,
        mesaj=mesaj,
        suma_implicata=rotunjeste_bani(suma_implicata),
        zile_ramase=zile_ramase,
        actiune_recomandata=actiune_recomandata,
    )


def detecteaza_recurente(utilizator, azi):
    inceput_istoric = azi - timedelta(days=210)
    cheltuieli_istorice = Cheltuiala.objects.filter(
        utilizator=utilizator,
        data__gte=inceput_istoric,
        data__lt=azi,
    ).select_related('categorie').order_by('titlu', 'data')

    grupuri = {}
    for cheltuiala in cheltuieli_istorice:
        titlu_normalizat = (cheltuiala.titlu or '').strip().lower()
        if not titlu_normalizat:
            continue
        grupuri.setdefault(titlu_normalizat, []).append(cheltuiala)

    for _, elemente in grupuri.items():
        luni_distincte = {(item.data.year, item.data.month) for item in elemente}
        if len(luni_distincte) < 2:
            continue

        zile = [item.data.day for item in elemente]
        if max(zile) - min(zile) > 7:
            continue

        zi_medie = max(1, round(sum(zile) / len(zile)))
        exista_luna_curenta = any(item.data.year == azi.year and item.data.month == azi.month for item in elemente)

        if not exista_luna_curenta and azi.day <= zi_medie:
            an_tinta = azi.year
            luna_tinta = azi.month
        else:
            if azi.month == 12:
                an_tinta = azi.year + 1
                luna_tinta = 1
            else:
                an_tinta = azi.year
                luna_tinta = azi.month + 1

        zi_tinta = min(zi_medie, monthrange(an_tinta, luna_tinta)[1])
        data_urmatoare = date(an_tinta, luna_tinta, zi_tinta)
        zile_ramase = (data_urmatoare - azi).days

        if zile_ramase < 0 or zile_ramase > 40:
            continue

        ultima_cheltuiala = elemente[-1]
        suma_estimata = rotunjeste_bani(sum(item.suma for item in elemente) / Decimal(len(elemente)))
        mesaj = (
            f"Cheltuială recurentă detectată: {ultima_cheltuiala.titlu} apare în fiecare lună. "
            f"Urmează să apară în aproximativ {zile_ramase} zile cu o sumă estimată de {suma_estimata} RON."
        )
        actiune = 'Marchează ca așteptat sau setează reminder.'
        creeaza_alerta_daca_nu_exista(
            utilizator=utilizator,
            categorie=ultima_cheltuiala.categorie,
            tip='recurenta_detectata',
            mesaj=mesaj,
            suma_implicata=suma_estimata,
            zile_ramase=zile_ramase,
            actiune_recomandata=actiune,
        )


def calculate_forecasts(utilizator):
    azi = timezone.localdate()
    luna_curenta = azi.month
    an_curent = azi.year
    zile_trecute = max(azi.day, 1)
    zile_in_luna = monthrange(an_curent, luna_curenta)[1]
    zile_ramase_luna = max(zile_in_luna - zile_trecute, 0)
    data_sf_luna = date(an_curent, luna_curenta, zile_in_luna)

    totaluri_categorii = Cheltuiala.objects.filter(
        utilizator=utilizator,
        data__month=luna_curenta,
        data__year=an_curent,
    ).values('categorie').annotate(total=Sum('suma'))

    totaluri_map = {
        item['categorie']: Decimal(item['total'] or 0)
        for item in totaluri_categorii
    }

    luna_precedenta, an_precedent = (12, an_curent - 1) if luna_curenta == 1 else (luna_curenta - 1, an_curent)
    totaluri_precedente = Cheltuiala.objects.filter(
        utilizator=utilizator,
        data__month=luna_precedenta,
        data__year=an_precedent,
    ).values('categorie').annotate(total=Sum('suma'))

    totaluri_precedente_map = {
        item['categorie']: Decimal(item['total'] or 0)
        for item in totaluri_precedente
    }

    bugete_curente = Budget.objects.filter(
        utilizator=utilizator,
        luna=luna_curenta,
        an=an_curent,
    ).select_related('categorie')

    for buget in bugete_curente:
        suma_limita = Decimal(buget.suma_limita or 0)
        if suma_limita <= 0:
            continue

        total_cheltuit = Decimal(totaluri_map.get(buget.categorie_id, Decimal('0')) or 0)
        ritm_zilnic = total_cheltuit / Decimal(zile_trecute)
        proiectie_luna = ritm_zilnic * Decimal(zile_in_luna)
        procent_folosit = (total_cheltuit / suma_limita) * Decimal('100')
        procent_text = procent_folosit.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        suma_ramasa = rotunjeste_bani(max(suma_limita - total_cheltuit, Decimal('0')))

        suma_depasire = rotunjeste_bani(max(proiectie_luna - suma_limita, Decimal('0')))
        if suma_depasire > 0:
            mesaj = (
                f"La ritmul actual, vei depăși bugetul de {rotunjeste_bani(suma_limita)} RON pentru "
                f"{buget.categorie.nume} cu aproximativ {suma_depasire} RON până la sfârșitul lunii."
            )
            actiune = (
                f"Intră pe cheltuielile din {buget.categorie.nume} și prioritizează doar costurile "
                "esențiale pentru restul lunii."
            )
            creeaza_alerta_daca_nu_exista(
                utilizator=utilizator,
                categorie=buget.categorie,
                tip='depasire_iminenta',
                mesaj=mesaj,
                suma_implicata=suma_depasire,
                zile_ramase=zile_ramase_luna,
                actiune_recomandata=actiune,
            )
            continue

        if proiectie_luna > suma_limita * Decimal('0.85') and proiectie_luna < suma_limita:
            mesaj = (
                f"Ai cheltuit {procent_text}% din bugetul pentru {buget.categorie.nume} și mai sunt "
                f"{zile_ramase_luna} zile din lună. Încearcă să limitezi cheltuielile la {suma_ramasa} RON "
                f"până pe {data_sf_luna.strftime('%d.%m.%Y')}."
            )
            actiune = (
                f"Verifică zilnic categoria {buget.categorie.nume} și păstrează cheltuielile în limita de "
                f"{suma_ramasa} RON pentru restul lunii."
            )
            creeaza_alerta_daca_nu_exista(
                utilizator=utilizator,
                categorie=buget.categorie,
                tip='ritm_alert',
                mesaj=mesaj,
                suma_implicata=suma_ramasa,
                zile_ramase=zile_ramase_luna,
                actiune_recomandata=actiune,
            )

        if total_cheltuit < suma_limita * Decimal('0.5') and zile_trecute > 15:
            total_luna_precedenta = Decimal(totaluri_precedente_map.get(buget.categorie_id, Decimal('0')) or 0)
            economie = rotunjeste_bani(max(total_luna_precedenta - proiectie_luna, Decimal('0')))
            if economie > 0:
                mesaj = (
                    f"Ai cheltuit doar {procent_text}% din bugetul pentru {buget.categorie.nume}. "
                    f"Poți economisi până la {economie} RON față de luna trecută dacă menții același ritm."
                )
                actiune = (
                    f"Menține ritmul curent în {buget.categorie.nume}; proiecția lunară este "
                    f"{rotunjeste_bani(proiectie_luna)} RON."
                )
                creeaza_alerta_daca_nu_exista(
                    utilizator=utilizator,
                    categorie=buget.categorie,
                    tip='economie_posibila',
                    mesaj=mesaj,
                    suma_implicata=economie,
                    zile_ramase=zile_ramase_luna,
                    actiune_recomandata=actiune,
                )

    detecteaza_recurente(utilizator, azi)

    return list(
        ForecastAlert.objects.filter(utilizator=utilizator, citita=False)
        .select_related('categorie')
        .order_by('-creat_la')[:8]
    )


def obtine_filtre_luna_an(request):
    acum = timezone.now()
    luna = request.GET.get('month')
    an = request.GET.get('year')

    try:
        luna = int(luna)
    except (TypeError, ValueError):
        luna = acum.month

    try:
        an = int(an)
    except (TypeError, ValueError):
        an = acum.year

    if luna < 1 or luna > 12:
        luna = acum.month

    return luna, an


def cheltuieli_din_filtre(request):
    luna, an = obtine_filtre_luna_an(request)
    cheltuieli = Cheltuiala.objects.filter(
        utilizator=request.user,
        data__month=luna,
        data__year=an,
    ).select_related('categorie').order_by('-data', '-id')
    return cheltuieli, luna, an


def nume_fisier_export(luna, an, extensie):
    return f"spndix_cheltuieli_{luna:02d}_{an}.{extensie}"


def luna_display(luna):
    return dict(LUNA_CHOICES).get(luna, str(luna))


def luna_ani_disponibili(request):
    date_cheltuieli = Cheltuiala.objects.filter(utilizator=request.user).dates('data', 'year')
    ani = sorted({data.year for data in date_cheltuieli}, reverse=True)
    if not ani:
        ani = [timezone.now().year]
    return ani


def rezumat_cheltuieli_ai(request, luna, an):
    cheltuieli = Cheltuiala.objects.filter(
        utilizator=request.user,
        data__month=luna,
        data__year=an,
    ).select_related('categorie').order_by('-suma', 'categorie__nume')

    totaluri_categorii = list(
        cheltuieli.values('categorie__nume', 'categorie__culoare')
        .annotate(total=Sum('suma'))
        .order_by('-total')
    )

    bugete = Budget.objects.filter(
        utilizator=request.user,
        luna=luna,
        an=an,
    ).select_related('categorie')

    cheltuieli_detaliate = []
    for item in cheltuieli:
        cheltuieli_detaliate.append({
            'titlu': item.titlu,
            'categorie': item.categorie.nume if item.categorie else 'Fără categorie',
            'suma': float(item.suma),
            'data': item.data.strftime('%d.%m.%Y'),
            'descriere': item.descriere or '',
        })

    bugete_detaliate = []
    for buget in bugete:
        cheltuit = cheltuieli.filter(categorie=buget.categorie).aggregate(total=Sum('suma'))['total'] or Decimal('0')
        bugete_detaliate.append({
            'categorie': buget.categorie.nume,
            'suma_limita': float(buget.suma_limita),
            'suma_cheltuita': float(cheltuit),
            'procent': 0 if buget.suma_limita == 0 else round((float(cheltuit) / float(buget.suma_limita)) * 100, 1),
        })

    date_cheltuieli_text = json.dumps({
        'cheltuieli': cheltuieli_detaliate,
        'totaluri_pe_categorii': [
            {
                'categorie': item['categorie__nume'] or 'Fără categorie',
                'culoare': item['categorie__culoare'] or '#6c757d',
                'total': float(item['total']),
            }
            for item in totaluri_categorii
        ],
    }, ensure_ascii=False, indent=2)

    date_bugete_text = json.dumps(bugete_detaliate, ensure_ascii=False, indent=2)

    return date_cheltuieli_text, date_bugete_text, cheltuieli, totaluri_categorii, bugete_detaliate


def construieste_cheltuieli_detaliate(cheltuieli):
    linii = []
    for item in cheltuieli:
        categorie = item.categorie.nume if item.categorie else 'Fără categorie'
        linii.append(
            f"- [{item.data.strftime('%d.%m.%Y')}] {item.titlu} ({categorie}): {float(item.suma):.2f} RON"
        )
    return "\n".join(linii) if linii else "Nu există cheltuieli înregistrate pentru perioada selectată."


def obtine_luna_precedenta(luna, an):
    if luna == 1:
        return 12, an - 1
    return luna - 1, an


def construieste_date_luna_precedenta(utilizator, luna, an):
    luna_precedenta, an_precedent = obtine_luna_precedenta(luna, an)
    cheltuieli_precedente = Cheltuiala.objects.filter(
        utilizator=utilizator,
        data__month=luna_precedenta,
        data__year=an_precedent,
    ).select_related('categorie').order_by('-data', '-id')

    cheltuieli_text = construieste_cheltuieli_detaliate(cheltuieli_precedente)
    totaluri_categorii = list(
        cheltuieli_precedente.values('categorie__nume')
        .annotate(total=Sum('suma'))
        .order_by('-total')
    )

    if totaluri_categorii:
        totaluri_text = "\n".join(
            f"- {(item['categorie__nume'] or 'Fără categorie')}: {float(item['total']):.2f} RON"
            for item in totaluri_categorii
        )
    else:
        totaluri_text = "- Fără date"

    return (
        f"Luna precedentă analizată: {luna_display(luna_precedenta)} {an_precedent}\n"
        f"Cheltuieli detaliate:\n{cheltuieli_text}\n\n"
        "Totaluri pe categorii:\n"
        f"{totaluri_text}"
    )


def construieste_prompt_analiza(
    luna,
    an,
    tip_gospodarie,
    nr_persoane,
    are_copii,
    venit_lunar,
    obiectiv,
    date_cheltuieli_detaliate,
    date_bugete,
    date_luna_precedenta,
):
    return f"""
Ești un consilier financiar personal experimentat,
nu un chatbot generic. Analizezi cheltuielile reale
ale unui utilizator și dai sfaturi SPECIFICE bazate
EXCLUSIV pe datele lui, nu sfaturi generale.

CONTEXT UTILIZATOR:
- Tip gospodărie: {tip_gospodarie}
- Număr persoane în gospodărie: {nr_persoane}
- Are copii: {are_copii}
- Venit lunar aproximativ: {venit_lunar} RON
- Obiectiv financiar: {obiectiv}

CHELTUIELI LUNA {luna} {an}:
{date_cheltuieli_detaliate}

BUGETE SETATE:
{date_bugete}

CHELTUIELI LUNA PRECEDENTĂ (pentru comparație):
{date_luna_precedenta}

REGULI STRICTE:
1. NU da sfaturi generice - doar sfaturi bazate
   pe datele CONCRETE ale acestui utilizator
2. Calculează cheltuielile per persoană din
   gospodărie unde e relevant
3. Compară cu luna precedentă și identifică
   ce a crescut/scăzut
4. Identifică anomalii specifice cu sume exacte
5. Sfaturile trebuie să fie ACȚIONABILE cu sume exacte:
   NU: "Reduce cheltuielile pe divertisment"
   DA: "Ai plătit Netflix (45 RON) + HBO (35 RON) =
       80 RON. Dacă împarți Netflix cu cineva
       economisești 45 RON/lună = 540 RON/an"
6. Dacă sunt sub 10 cheltuieli introduse, menționează
   că analiza e limitată și îndeamnă să adauge mai multe
7. Ține cont de contextul familial - nu sugera reducerea
   cheltuielilor esențiale pentru familie dacă sunt
   rezonabile per persoană
8. Tonul să fie ca al unui prieten care ajută,
   nu ca un profesor care ceartă

STRUCTURĂ RĂSPUNS (respectă exact această structură):
1. Sumar luna {luna} {an} (3-4 rânduri cu totaluri exacte)
2. Top 3 categorii cu cele mai mari cheltuieli
   (sume exacte + comparație cu luna precedentă)
3. O anomalie sau pattern interesant observat în date
4. 3 sfaturi SPECIFICE și ACȚIONABILE cu sume exacte
5. Estimare economii: dacă urmezi sfaturile,
   cât poți economisi luna viitoare?

Răspunde în română, prietenos și direct.
"""


def genereaza_text_gemini(prompt):
    modele_candidate = (
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite',
        'gemini-flash-lite-latest',
        'gemini-1.5-flash-latest',
    )
    ultima_eroare = None

    for model_name in modele_candidate:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            raspuns = (response.text or '').strip()
            if raspuns:
                return raspuns
            ultima_eroare = RuntimeError(f'Modelul {model_name} a returnat răspuns gol.')
        except Exception as exc:
            ultima_eroare = exc

    raise RuntimeError(
        'Nu am găsit un model Gemini compatibil pentru analiză. '
        f'Ultima eroare: {ultima_eroare}'
    )


def construieste_descriere_bon(produse, magazin, data_cumpararii, categorie_sugerata):
    linii = [f"{produs.get('nume', 'Produs')}: {float(produs.get('pret', 0)):.2f} RON" for produs in produse]
    bloc_produse = "\n".join(f"- {linie}" for linie in linii) if linii else "- Nu au fost extrase produse individuale."
    return (
        f"Bon scanat automat.\n"
        f"Magazin: {magazin}\n"
        f"Data extrasă: {data_cumpararii}\n"
        f"Categorie sugerată: {categorie_sugerata or '—'}\n\n"
        f"Produse extrase:\n{bloc_produse}"
    )


def curata_json_text(text):
    curat = text.strip()
    if curat.startswith('```'):
        curat = re.sub(r'^```(?:json)?\s*', '', curat, flags=re.IGNORECASE | re.DOTALL)
        curat = re.sub(r'\s*```$', '', curat, flags=re.DOTALL).strip()
    if not curat.startswith('{'):
        start = curat.find('{')
        end = curat.rfind('}')
        if start != -1 and end != -1:
            curat = curat[start:end + 1]
    return json.loads(curat)


def pregateste_bon_upload(uploaded_file):
    extensie = Path(uploaded_file.name).suffix.lower()
    if extensie not in ['.jpg', '.jpeg', '.png', '.pdf']:
        raise ValueError('Sunt acceptate doar fișiere JPG, PNG sau PDF.')

    file_bytes = uploaded_file.read()
    identificator = uuid.uuid4().hex
    fisier_original_relativ = f'bonuri/{identificator}{extensie or ".bin"}'
    fisier_original_salvat = default_storage.save(fisier_original_relativ, ContentFile(file_bytes))
    original_url = default_storage.url(fisier_original_salvat)
    original_path = default_storage.path(fisier_original_salvat)

    preview_url = original_url
    imagine_path = original_path

    if extensie == '.pdf':
        try:
            reader = PdfReader(BytesIO(file_bytes))
        except Exception as exc:
            raise ValueError('Fișierul PDF nu poate fi citit.') from exc

        if not reader.pages:
            raise ValueError('PDF-ul nu conține pagini valide.')

        prima_pagina = reader.pages[0]
        imagini = list(prima_pagina.images)
        if not imagini:
            raise ValueError('PDF-ul nu conține o imagine pe prima pagină. Încarcă un PDF scanat sau JPG/PNG.')

        imagine_pdf = imagini[0]
        try:
            imagine = PIL.Image.open(BytesIO(imagine_pdf.data))
            imagine = ImageOps.exif_transpose(imagine)
            if imagine.mode not in ['RGB', 'L']:
                imagine = imagine.convert('RGB')
        except UnidentifiedImageError as exc:
            raise ValueError('Imaginea extrasă din PDF nu este validă.') from exc

        preview_buffer = BytesIO()
        imagine.save(preview_buffer, format='PNG')
        preview_relativ = f'bonuri/{identificator}_preview.png'
        preview_salvat = default_storage.save(preview_relativ, ContentFile(preview_buffer.getvalue()))
        preview_url = default_storage.url(preview_salvat)
        imagine_path = default_storage.path(preview_salvat)
    else:
        try:
            imagine = PIL.Image.open(BytesIO(file_bytes))
            imagine = ImageOps.exif_transpose(imagine)
            if imagine.mode not in ['RGB', 'L']:
                imagine = imagine.convert('RGB')
        except UnidentifiedImageError as exc:
            raise ValueError('Fișierul încărcat nu este o imagine validă.') from exc

    return {
        'original_url': original_url,
        'preview_url': preview_url,
        'stored_path': fisier_original_salvat,
        'imagine_path': imagine_path,
        'filename': uploaded_file.name,
    }
def analizeaza_bon_cu_gemini(imagine_path):
    prompt = (
        "Analizează acest bon de cumpărături și extrage:\n"
        "1. Numele magazinului\n"
        "2. Data cumpărăturii\n"
        "3. Lista produselor cu prețurile lor\n"
        "4. Totalul bonului\n"
        "5. Categoria sugerată (Food & Groceries, Electronics, etc.)\n"
        "Răspunde DOAR în format JSON cu structura:\n"
        "{\n"
        '  "magazin": "nume",\n'
        '  "data": "YYYY-MM-DD",\n'
        '  "produse": [{"nume": "...", "pret": 0.00}],\n'
        '  "total": 0.00,\n'
        '  "categorie_sugerata": "..."\n'
        "}"
    )

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-flash-lite-latest')
    imagine = PIL.Image.open(imagine_path)
    response = model.generate_content([prompt, imagine])
    response_text = (response.text or '').strip()
    return curata_json_text(response_text), response_text


def obtine_date_bon_din_sesiune(request):
    return request.session.get('bon_scan_data')


def salveaza_date_bon_in_sesiune(request, scan_data):
    request.session['bon_scan_data'] = scan_data
    request.session.modified = True


def sterge_date_bon_din_sesiune(request):
    if 'bon_scan_data' in request.session:
        del request.session['bon_scan_data']
        request.session.modified = True


@login_required
def scaneaza_bon(request):
    categorii = Categorie.objects.all().order_by('nume')
    bon_scan_data = obtine_date_bon_din_sesiune(request)

    if request.method == 'POST':
        actiune = request.POST.get('action')

        if actiune == 'analizeaza':
            fisier = request.FILES.get('bon_fisier')
            if not fisier:
                messages.error(request, 'Alege un fișier JPG, PNG sau PDF înainte de analiză.')
                return redirect('scaneaza_bon')

            try:
                pregatit = pregateste_bon_upload(fisier)
                analiza_json, text_brut = analizeaza_bon_cu_gemini(pregatit['imagine_path'])

                magazin = str(analiza_json.get('magazin', '')).strip() or 'Bon scanat'
                data_text = str(analiza_json.get('data', '')).strip()
                produse = analiza_json.get('produse', []) or []
                total = Decimal(str(analiza_json.get('total', 0))).quantize(Decimal('0.01'))
                categorie_sugerata = str(analiza_json.get('categorie_sugerata', '')).strip()
                data_cumpararii = data_text or timezone.now().date().isoformat()

                categorie_initiala = Categorie.objects.filter(nume__iexact=categorie_sugerata).first()
                descriere = construieste_descriere_bon(produse, magazin, data_cumpararii, categorie_sugerata)

                scan_data = {
                    'file_url': pregatit['preview_url'],
                    'original_url': pregatit['original_url'],
                    'stored_path': pregatit['stored_path'],
                    'magazin': magazin,
                    'data_cumpararii': data_cumpararii,
                    'produse': produse,
                    'total': float(total),
                    'categorie_sugerata': categorie_sugerata,
                    'categorie_initiala_id': categorie_initiala.pk if categorie_initiala else None,
                    'titlu_propus': f'Bon - {magazin}',
                    'descriere_propusa': descriere,
                    'raw_response': text_brut,
                }
                salveaza_date_bon_in_sesiune(request, scan_data)
                messages.success(request, 'Bonul a fost analizat cu succes.')
                return redirect('scaneaza_bon')
            except Exception as exc:
                messages.error(request, f'Nu s-a putut analiza bonul: {exc}')
                return redirect('scaneaza_bon')

        if actiune == 'salveaza':
            if not bon_scan_data:
                messages.error(request, 'Nu există date de bon salvate pentru confirmare.')
                return redirect('scaneaza_bon')

            titlu = request.POST.get('titlu', '').strip() or bon_scan_data.get('titlu_propus', 'Bon scanat')
            total_text = request.POST.get('total', '').strip()
            categorie_sugerata_text = request.POST.get('categorie_sugerata', '').strip()
            categorie_id = request.POST.get('categorie') or ''
            categorie = None
            if categorie_id:
                categorie = Categorie.objects.filter(pk=categorie_id).first()
            if not categorie and categorie_sugerata_text:
                categorie = Categorie.objects.filter(nume__iexact=categorie_sugerata_text).first()
            if not categorie and bon_scan_data.get('categorie_initiala_id'):
                categorie = Categorie.objects.filter(pk=bon_scan_data['categorie_initiala_id']).first()

            data_cumpararii_text = request.POST.get('data_cumpararii', bon_scan_data.get('data_cumpararii'))
            try:
                data_cumpararii = date.fromisoformat(data_cumpararii_text)
            except Exception:
                data_cumpararii = timezone.now().date()

            descriere = request.POST.get('descriere', '').strip() or bon_scan_data.get('descriere_propusa', '')
            try:
                suma = Decimal(total_text or str(bon_scan_data.get('total', 0))).quantize(Decimal('0.01'))
            except Exception:
                suma = Decimal(str(bon_scan_data.get('total', 0))).quantize(Decimal('0.01'))

            cheltuiala = Cheltuiala.objects.create(
                utilizator=request.user,
                categorie=categorie,
                titlu=titlu,
                suma=suma,
                data=data_cumpararii,
                descriere=descriere,
            )
            sterge_date_bon_din_sesiune(request)
            messages.success(request, f'Cheltuiala "{cheltuiala.titlu}" a fost creată din bon!')
            return redirect('lista_cheltuieli')

    context = {
        'categorii': categorii,
        'bon_scan': bon_scan_data,
    }
    return render(request, 'spndix/scaneaza_bon.html', context)


def genereaza_analiza_ai(request, luna, an, force=False):
    existing = AIAnaliza.objects.filter(utilizator=request.user, luna=luna, an=an).first()
    if existing and not force:
        return existing, False

    if not settings.GEMINI_API_KEY:
        raise RuntimeError('Lipsește cheia GEMINI_API_KEY din .env')

    _, date_bugete_text, _, _, _ = rezumat_cheltuieli_ai(request, luna, an)

    try:
        profil = request.user.userprofile
        tip_gospodarie = profil.get_tip_gospodarie_display()
        nr_persoane = profil.nr_persoane
        are_copii = "Da" if profil.are_copii else "Nu"
        venit_lunar = profil.venit_lunar or "Nespecificat"
        obiectiv = profil.get_obiectiv_display()
    except UserProfile.DoesNotExist:
        tip_gospodarie = "Nespecificat"
        nr_persoane = 1
        are_copii = "Nu"
        venit_lunar = "Nespecificat"
        obiectiv = "Nespecificat"

    cheltuieli_luna = Cheltuiala.objects.filter(
        utilizator=request.user,
        data__month=luna,
        data__year=an,
    ).select_related('categorie').order_by('-data', '-id')

    date_cheltuieli_detaliate = construieste_cheltuieli_detaliate(cheltuieli_luna)
    date_luna_precedenta = construieste_date_luna_precedenta(request.user, luna, an)

    prompt = construieste_prompt_analiza(
        luna=luna_display(luna),
        an=an,
        tip_gospodarie=tip_gospodarie,
        nr_persoane=nr_persoane,
        are_copii=are_copii,
        venit_lunar=venit_lunar,
        obiectiv=obiectiv,
        date_cheltuieli_detaliate=date_cheltuieli_detaliate,
        date_bugete=date_bugete_text,
        date_luna_precedenta=date_luna_precedenta,
    )

    genai.configure(api_key=settings.GEMINI_API_KEY)
    analysis_text = genereaza_text_gemini(prompt)

    if existing:
        existing.continut_analiza = analysis_text
        existing.creat_la = timezone.now()
        existing.save(update_fields=['continut_analiza', 'creat_la'])
        return existing, True

    return AIAnaliza.objects.create(
        utilizator=request.user,
        luna=luna,
        an=an,
        continut_analiza=analysis_text,
    ), True


@login_required
def dashboard(request):
    azi = timezone.now()
    luna_curenta = azi.month
    an_curent = azi.year

    total_luna = Cheltuiala.objects.filter(
        utilizator=request.user,
        data__month=luna_curenta,
        data__year=an_curent
    ).aggregate(total=Sum('suma'))['total'] or 0

    total_general = Cheltuiala.objects.filter(
        utilizator=request.user
    ).aggregate(total=Sum('suma'))['total'] or 0

    ultimele_cheltuieli = Cheltuiala.objects.filter(
        utilizator=request.user
    )[:5]

    bugete_curente = Budget.objects.filter(
        utilizator=request.user,
        luna=luna_curenta,
        an=an_curent,
    ).select_related('categorie')

    bugete_dashboard = [construieste_buget_dashboard(buget, request.user) for buget in bugete_curente]
    bugete_depasite = [buget for buget in bugete_dashboard if buget['excedat']]

    categorii_data = Cheltuiala.objects.filter(
        utilizator=request.user,
        data__month=luna_curenta,
        data__year=an_curent
    ).values('categorie__nume').annotate(total=Sum('suma'))

    pie_labels = [item['categorie__nume'] or 'Fără categorie' for item in categorii_data]
    pie_data = [float(item['total']) for item in categorii_data]

    bar_labels = []
    bar_data = []
    for i in range(5, -1, -1):
        if luna_curenta - i <= 0:
            luna = luna_curenta - i + 12
            an = an_curent - 1
        else:
            luna = luna_curenta - i
            an = an_curent

        total = Cheltuiala.objects.filter(
            utilizator=request.user,
            data__month=luna,
            data__year=an
        ).aggregate(total=Sum('suma'))['total'] or 0

        nume_luna = ['Ian', 'Feb', 'Mar', 'Apr', 'Mai', 'Iun',
                     'Iul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][luna - 1]
        bar_labels.append(nume_luna)
        bar_data.append(float(total))

    forecast_alerts = calculate_forecasts(request.user)

    context = {
        'total_luna': total_luna,
        'total_general': total_general,
        'ultimele_cheltuieli': ultimele_cheltuieli,
        'bugete_dashboard': bugete_dashboard,
        'bugete_depasite': bugete_depasite,
        'pie_labels': json.dumps(pie_labels),
        'pie_data': json.dumps(pie_data),
        'bar_labels': json.dumps(bar_labels),
        'bar_data': json.dumps(bar_data),
        'luna_curenta': azi.strftime('%B %Y'),
        'forecast_alerts': forecast_alerts,
    }
    return render(request, 'spndix/dashboard.html', context)


@login_required
def marca_citita(request, pk):
    alerta = get_object_or_404(ForecastAlert, pk=pk, utilizator=request.user)
    if not alerta.citita:
        alerta.citita = True
        alerta.save(update_fields=['citita'])

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('dashboard')

@login_required
def lista_cheltuieli(request):
    cheltuieli = Cheltuiala.objects.filter(utilizator=request.user).select_related('categorie').order_by('-data', '-id')
    luna_selectata, an_selectat = obtine_filtre_luna_an(request)
    categorie_selectata = request.GET.get('categorie')

    cheltuieli_filtrate = cheltuieli.filter(data__month=luna_selectata, data__year=an_selectat)
    if categorie_selectata:
        try:
            categorie_selectata = int(categorie_selectata)
            cheltuieli_filtrate = cheltuieli_filtrate.filter(categorie_id=categorie_selectata)
        except (TypeError, ValueError):
            categorie_selectata = None

    total_cheltuit = cheltuieli_filtrate.aggregate(total=Sum('suma'))['total'] or 0
    ani_disponibili = sorted(
        set(
            Cheltuiala.objects.filter(utilizator=request.user).dates('data', 'year')
        ),
        reverse=True,
    )
    ani_disponibili = [data.year for data in ani_disponibili]
    if an_selectat not in ani_disponibili:
        ani_disponibili.insert(0, an_selectat)

    context = {
        'cheltuieli': cheltuieli_filtrate,
        'total_cheltuit': total_cheltuit,
        'luna_selectata': luna_selectata,
        'an_selectat': an_selectat,
        'categorie_selectata': categorie_selectata,
        'luni': LUNA_CHOICES,
        'ani_disponibili': sorted(set(ani_disponibili), reverse=True),
    }
    return render(request, 'spndix/lista.html', context)


@login_required
def analiza_ai(request):
    luna_selectata, an_selectat = obtine_filtre_luna_an(request)
    cheltuieli_count = Cheltuiala.objects.filter(
        utilizator=request.user,
        data__month=luna_selectata,
        data__year=an_selectat,
    ).count()
    warning_date_insuficiente = cheltuieli_count < 10

    if request.method == 'POST':
        luna_selectata = int(request.POST.get('month', luna_selectata))
        an_selectat = int(request.POST.get('year', an_selectat))
        force = request.POST.get('force') == '1'

        try:
            analiza, created = genereaza_analiza_ai(request, luna_selectata, an_selectat, force=force)
            if created and force:
                messages.success(request, 'Analiza AI a fost regenerată cu succes.')
            elif created:
                messages.success(request, 'Analiza AI a fost generată cu succes.')
            else:
                messages.info(request, 'Analiza existentă a fost încărcată.')
            return redirect(f"{request.path}?month={luna_selectata}&year={an_selectat}")
        except Exception as exc:
            messages.error(request, f'Nu s-a putut genera analiza AI: {exc}')
            return redirect(f"{request.path}?month={luna_selectata}&year={an_selectat}")

    analiza = AIAnaliza.objects.filter(
        utilizator=request.user,
        luna=luna_selectata,
        an=an_selectat,
    ).first()

    if analiza:
        context = {
            'luna_selectata': luna_selectata,
            'an_selectat': an_selectat,
            'ani_disponibili': luna_ani_disponibili(request),
            'luni': LUNA_CHOICES,
            'analiza': analiza,
            'analiza_exista': True,
            'creata_azi': False,
            'cheltuieli_count': cheltuieli_count,
            'warning_date_insuficiente': warning_date_insuficiente,
        }
    else:
        date_cheltuieli_text, date_bugete_text, cheltuieli, totaluri_categorii, bugete_detaliate = rezumat_cheltuieli_ai(request, luna_selectata, an_selectat)
        context = {
            'luna_selectata': luna_selectata,
            'an_selectat': an_selectat,
            'ani_disponibili': luna_ani_disponibili(request),
            'luni': LUNA_CHOICES,
            'analiza': None,
            'analiza_exista': False,
            'creata_azi': False,
            'date_cheltuieli_text': date_cheltuieli_text,
            'date_bugete_text': date_bugete_text,
            'cheltuieli_count': cheltuieli.count(),
            'categorii_count': len(totaluri_categorii),
            'bugete_count': len(bugete_detaliate),
            'warning_date_insuficiente': warning_date_insuficiente,
        }

    return render(request, 'spndix/analiza.html', context)


@login_required
def export_cheltuieli_excel(request):
    cheltuieli, luna, an = cheltuieli_din_filtre(request)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Cheltuieli'

    ws.merge_cells('A1:E1')
    ws['A1'] = 'Spndix - Export Cheltuieli'
    ws['A1'].font = Font(bold=True, color='FFFFFF', size=14)
    ws['A1'].fill = PatternFill('solid', fgColor='1F4E78')
    ws['A1'].alignment = Alignment(horizontal='center')

    ws.append([f'Perioada: {luna_display(luna)} {an}', '', '', '', ''])
    ws.append(['Titlu', 'Categorie', 'Suma', 'Data', 'Descriere'])

    header_fill = PatternFill('solid', fgColor='1F4E78')
    header_font = Font(color='FFFFFF', bold=True)
    thin = Side(style='thin', color='D9D9D9')
    total = 0

    for cell in ws[3]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    row_index = 4
    for cheltuiala in cheltuieli:
        categorie = cheltuiala.categorie.nume if cheltuiala.categorie else 'Fără categorie'
        ws.append([
            cheltuiala.titlu,
            categorie,
            float(cheltuiala.suma),
            cheltuiala.data.strftime('%d.%m.%Y'),
            cheltuiala.descriere or '',
        ])
        total += float(cheltuiala.suma)
        for col in range(1, 6):
            ws.cell(row=row_index, column=col).border = Border(left=thin, right=thin, top=thin, bottom=thin)
        row_index += 1

    ws.append(['', '', 'Total', total, ''])
    total_row = ws.max_row
    for cell in ws[total_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill('solid', fgColor='D9EAF7')
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for column, width in {'A': 28, 'B': 26, 'C': 14, 'D': 14, 'E': 36}.items():
        ws.column_dimensions[column].width = width

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nume_fisier_export(luna, an, "xlsx")}"'

    output = BytesIO()
    wb.save(output)
    response.write(output.getvalue())
    return response


@login_required
def export_cheltuieli_pdf(request):
    cheltuieli, luna, an = cheltuieli_din_filtre(request)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SpndixTitle', parent=styles['Title'], fontSize=18, leading=22, textColor=colors.HexColor('#1F4E78')))
    styles.add(ParagraphStyle(name='SpndixSub', parent=styles['Normal'], fontSize=10, leading=12, textColor=colors.HexColor('#555555')))

    elements = [
        Paragraph('Spndix', styles['SpndixTitle']),
        Paragraph(f'Export Cheltuieli - {luna_display(luna)} {an}', styles['SpndixSub']),
        Spacer(1, 0.4 * cm),
    ]

    data = [['Titlu', 'Categorie', 'Suma', 'Data', 'Descriere']]
    total = 0
    for cheltuiala in cheltuieli:
        categorie = cheltuiala.categorie.nume if cheltuiala.categorie else 'Fără categorie'
        data.append([
            cheltuiala.titlu,
            categorie,
            f"{cheltuiala.suma:.2f} RON",
            cheltuiala.data.strftime('%d.%m.%Y'),
            cheltuiala.descriere or '',
        ])
        total += float(cheltuiala.suma)

    data.append(['', '', f'Total: {total:.2f} RON', '', ''])

    table = Table(data, colWidths=[6.0 * cm, 5.0 * cm, 3.5 * cm, 3.2 * cm, 7.5 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.whitesmoke, colors.HexColor('#EAF2F8')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D9EAF7')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('SPAN', (0, -1), (1, -1)),
        ('ALIGN', (0, -1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nume_fisier_export(luna, an, "pdf")}"'
    response.write(pdf)
    return response

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
    return render(
        request,
        'spndix/form.html',
        {
            'form': form,
            'titlu': 'Adaugă Cheltuială',
            'cancel_url': 'lista_cheltuieli',
            'show_scan_receipt_cta': True,
        },
    )

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
    return render(request, 'spndix/form.html', {'form': form, 'titlu': 'Editează Cheltuială', 'cancel_url': 'lista_cheltuieli'})

@login_required
def sterge_cheltuiala(request, pk):
    cheltuiala = get_object_or_404(Cheltuiala, pk=pk, utilizator=request.user)
    if request.method == 'POST':
        cheltuiala.delete()
        messages.success(request, f'Cheltuiala "{cheltuiala.titlu}" a fost ștearsă!')
        return redirect('lista_cheltuieli')
    return render(request, 'spndix/confirmare_stergere.html', {'cheltuiala': cheltuiala, 'back_url': 'lista_cheltuieli'})


@login_required
def lista_bugete(request):
    bugete = Budget.objects.filter(utilizator=request.user).select_related('categorie')
    bugete_utile = [construieste_buget_dashboard(buget, request.user) for buget in bugete]
    return render(request, 'spndix/bugete/lista.html', {'bugete': bugete_utile})


@login_required
def adauga_buget(request):
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            buget = form.save(commit=False)
            buget.utilizator = request.user
            buget.save()
            messages.success(request, f'Bugetul pentru {buget.categorie.nume} a fost adăugat!')
            return redirect('lista_bugete')
    else:
        form = BudgetForm()
    return render(request, 'spndix/form.html', {'form': form, 'titlu': 'Adaugă Buget', 'cancel_url': 'lista_bugete'})


@login_required
def editeaza_buget(request, pk):
    buget = get_object_or_404(Budget, pk=pk, utilizator=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=buget)
        if form.is_valid():
            form.save()
            messages.success(request, f'Bugetul pentru {buget.categorie.nume} a fost actualizat!')
            return redirect('lista_bugete')
    else:
        form = BudgetForm(instance=buget)
    return render(request, 'spndix/form.html', {'form': form, 'titlu': 'Editează Buget', 'cancel_url': 'lista_bugete'})


@login_required
def sterge_buget(request, pk):
    buget = get_object_or_404(Budget, pk=pk, utilizator=request.user)
    if request.method == 'POST':
        buget.delete()
        messages.success(request, 'Bugetul a fost șters!')
        return redirect('lista_bugete')
    return render(request, 'spndix/confirmare_stergere.html', {'cheltuiala': buget, 'back_url': 'lista_bugete'})


@login_required
def profil(request):
    profil_user, _ = UserProfile.objects.get_or_create(utilizator=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profil_user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profilul a fost salvat cu succes.')
            return redirect('profil')
    else:
        form = UserProfileForm(instance=profil_user)

    return render(request, 'spndix/profil.html', {'form': form})


def register(request):
    if request.user.is_authenticated:
        return redirect('lista_cheltuieli')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Cont creat cu succes! Bun venit, {user.username}!')
            return redirect('lista_cheltuieli')
    else:
        form = RegisterForm()
    return render(request, 'spndix/register.html', {'form': form})