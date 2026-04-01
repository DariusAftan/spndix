from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Cheltuiala, Categorie, Budget, AIAnaliza, LUNA_CHOICES
from .forms import CheltuialaForm, RegisterForm, BudgetForm
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
from decimal import Decimal
from pathlib import Path
from datetime import date

import fitz
import PIL.Image
from PIL import ImageOps, UnidentifiedImageError
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


def construieste_prompt_analiza(luna, an, date_cheltuieli, date_bugete):
    return (
        "Ești un asistent financiar personal. Analizează cheltuielile acestui utilizator "
        f"pentru luna {luna_display(luna)} {an}:\n"
        f"{date_cheltuieli}\n"
        f"Bugete setate: {date_bugete}\n"
        "Te rog să:\n"
        "1. Identifici categoriile unde s-a cheltuit cel mai mult\n"
        "2. Compari cheltuielile cu bugetele setate\n"
        "3. Sugerezi unde s-ar fi putut economisi\n"
        "4. Dai 3 sfaturi concrete pentru luna viitoare\n"
        "Răspunde în română, într-un mod prietenos și constructiv."
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
        document = fitz.open(stream=file_bytes, filetype='pdf')
        pagina = document.load_page(0)
        pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        preview_relativ = f'bonuri/{identificator}_preview.png'
        preview_salvat = default_storage.save(preview_relativ, ContentFile(pix.tobytes('png')))
        preview_url = default_storage.url(preview_salvat)
        imagine_path = default_storage.path(preview_salvat)
        document.close()
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
            categorie_id = request.POST.get('categorie') or ''
            categorie = None
            if categorie_id:
                categorie = Categorie.objects.filter(pk=categorie_id).first()
            if not categorie and bon_scan_data.get('categorie_initiala_id'):
                categorie = Categorie.objects.filter(pk=bon_scan_data['categorie_initiala_id']).first()

            data_cumpararii_text = request.POST.get('data_cumpararii', bon_scan_data.get('data_cumpararii'))
            try:
                data_cumpararii = date.fromisoformat(data_cumpararii_text)
            except Exception:
                data_cumpararii = timezone.now().date()

            descriere = request.POST.get('descriere', '').strip() or bon_scan_data.get('descriere_propusa', '')
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

    date_cheltuieli_text, date_bugete_text, _, _, _ = rezumat_cheltuieli_ai(request, luna, an)
    prompt = construieste_prompt_analiza(luna, an, date_cheltuieli_text, date_bugete_text)

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    analysis_text = (response.text or '').strip()

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

    # Total luna curenta
    total_luna = Cheltuiala.objects.filter(
        utilizator=request.user,
        data__month=luna_curenta,
        data__year=an_curent
    ).aggregate(total=Sum('suma'))['total'] or 0

    # Total general
    total_general = Cheltuiala.objects.filter(
        utilizator=request.user
    ).aggregate(total=Sum('suma'))['total'] or 0

    # Ultimele 5 cheltuieli
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

    # Date pentru grafic pie - cheltuieli pe categorii (luna curenta)
    categorii_data = Cheltuiala.objects.filter(
        utilizator=request.user,
        data__month=luna_curenta,
        data__year=an_curent
    ).values('categorie__nume').annotate(total=Sum('suma'))

    pie_labels = [item['categorie__nume'] or 'Fără categorie' for item in categorii_data]
    pie_data = [float(item['total']) for item in categorii_data]

    # Date pentru grafic bar - ultimele 6 luni
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
    }
    return render(request, 'spndix/dashboard.html', context)

@login_required
def lista_cheltuieli(request):
    cheltuieli = Cheltuiala.objects.filter(utilizator=request.user).select_related('categorie').order_by('-data', '-id')
    luna_selectata, an_selectat = obtine_filtre_luna_an(request)

    cheltuieli_filtrate = cheltuieli.filter(data__month=luna_selectata, data__year=an_selectat)
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
        'luna_selectata': luna_selectata,
        'an_selectat': an_selectat,
        'luni': LUNA_CHOICES,
        'ani_disponibili': sorted(set(ani_disponibili), reverse=True),
    }
    return render(request, 'spndix/lista.html', context)


@login_required
def analiza_ai(request):
    luna_selectata, an_selectat = obtine_filtre_luna_an(request)

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
    return render(request, 'spndix/form.html', {'form': form, 'titlu': 'Adaugă Cheltuială', 'cancel_url': 'lista_cheltuieli'})

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