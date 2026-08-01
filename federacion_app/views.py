from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import date, datetime

from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from .models import Persona, SolicitudPase, Vinculo, DocumentoSolicitud, Club, Categoria
from .forms import SolicitudPaseForm, ResolucionSolicitudForm


def es_delegado(usuario):
    return usuario.is_authenticated and usuario.rol == "delegado"


def es_federacion(usuario):
    return usuario.is_authenticated and usuario.rol == "federacion"


def _notificar_pedido_jugador(solicitud):
    """
    Le avisa por email a los delegados del club de origen que otro club
    pidió a uno de sus jugadores. Si el envío falla (mal configurado el
    email, sin internet, etc.) no rompe el flujo: solo lo ignora.
    """
    from .models import Usuario
    destinatarios = list(
        Usuario.objects.filter(rol="delegado", club=solicitud.club_origen)
        .exclude(email="").values_list("email", flat=True)
    )
    if not destinatarios:
        return
    try:
        send_mail(
            subject=f"[Federación] {solicitud.club_destino} pidió a {solicitud.persona}",
            message=(
                f"Hola,\n\n"
                f"El club {solicitud.club_destino} solicitó el pase de {solicitud.persona} "
                f"(documento {solicitud.persona.documento}), que figura en tu club, {solicitud.club_origen}.\n\n"
                f"Entrá al sistema para revisar y liberar o rechazar la solicitud:\n"
                f"http://127.0.0.1:8000/solicitudes/liberar/\n\n"
                f"— Federación Fueguina de Futsal"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=destinatarios,
            fail_silently=True,
        )
    except Exception:
        pass


def bienvenida(request):
    """Pantalla pública de entrada, con logo y foto de fondo de la federación."""
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "federacion_app/bienvenida.html")


@login_required
def home(request):
    """Después del login, manda a cada usuario a su pantalla principal."""
    if request.user.rol == "delegado":
        return redirect("mis_solicitudes")
    elif request.user.rol == "federacion":
        return redirect("panel_solicitudes")
    return redirect("buscar_persona")


# ---------------------------------------------------------------------
# PANTALLA 1: el delegado carga una nueva solicitud
# ---------------------------------------------------------------------

@login_required
@user_passes_test(es_delegado)
def nueva_solicitud(request):
    if request.method == "POST":
        form = SolicitudPaseForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.cleaned_data["documento"]

            # Busca la persona o la crea si es un alta nueva
            persona, creada = Persona.objects.get_or_create(
                documento=documento,
                defaults={
                    "tipo": "jugador",
                    "nombre": form.cleaned_data.get("nombre", ""),
                    "apellido": form.cleaned_data.get("apellido", ""),
                    "fecha_nacimiento": form.cleaned_data.get("fecha_nacimiento") or date.today(),
                    "foto": form.cleaned_data.get("foto"),
                    "numero_carnet": form.cleaned_data.get("numero_carnet", ""),
                    "requiere_carnet": form.cleaned_data.get("requiere_carnet", False),
                },
            )

            club_origen = persona.club_actual if not creada else None

            # Si es un pase real entre dos clubes distintos, primero tiene
            # que liberarlo el club de origen. Si es alta nueva o cambio de
            # categoría dentro del mismo club, va directo a la federación.
            if club_origen and club_origen != request.user.club:
                estado_inicial = "pendiente_liberacion"
            else:
                estado_inicial = "pendiente"

            solicitud = SolicitudPase.objects.create(
                tipo=form.cleaned_data["tipo"],
                persona=persona,
                club_origen=club_origen,
                club_destino=request.user.club,
                categoria_destino=form.cleaned_data.get("categoria_destino"),
                creado_por=request.user,
                estado=estado_inicial,
            )

            archivo = form.cleaned_data.get("archivo_documentacion")
            if archivo:
                DocumentoSolicitud.objects.create(solicitud=solicitud, archivo=archivo)

            if estado_inicial == "pendiente_liberacion":
                _notificar_pedido_jugador(solicitud)

            messages.success(request, "Solicitud enviada. La federación la va a revisar.")
            return redirect("mis_solicitudes")
    else:
        form = SolicitudPaseForm()

    return render(request, "federacion_app/nueva_solicitud.html", {"form": form})


@login_required
@user_passes_test(es_delegado)
def mis_solicitudes(request):
    """Bandeja: solo las solicitudes que todavía están en trámite."""
    solicitudes = SolicitudPase.objects.filter(
        club_destino=request.user.club
    ).exclude(estado__in=["aprobado", "rechazado"]).select_related("persona", "club_origen", "club_destino")
    return render(request, "federacion_app/mis_solicitudes.html", {"solicitudes": solicitudes})


@login_required
@user_passes_test(es_delegado)
def historial_mis_solicitudes(request):
    """Historial: solicitudes ya resueltas (aprobadas o rechazadas)."""
    solicitudes = SolicitudPase.objects.filter(
        club_destino=request.user.club, estado__in=["aprobado", "rechazado"]
    ).select_related("persona", "club_origen", "club_destino")
    return render(request, "federacion_app/historial_solicitudes.html", {"solicitudes": solicitudes})


@login_required
@user_passes_test(es_delegado)
def solicitudes_a_liberar(request):
    """
    Bandeja del delegado del club de ORIGEN: acá ve los pedidos que
    otros clubes hicieron por jugadores suyos, y puede liberarlos o
    rechazarlos antes de que pasen a la federación.
    """
    solicitudes = SolicitudPase.objects.filter(
        club_origen=request.user.club, estado="pendiente_liberacion"
    ).select_related("persona", "club_destino")
    return render(request, "federacion_app/solicitudes_a_liberar.html", {"solicitudes": solicitudes})


@login_required
@user_passes_test(es_delegado)
def liberar_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(
        SolicitudPase, id=solicitud_id, club_origen=request.user.club, estado="pendiente_liberacion"
    )

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "liberar":
            nota = request.POST.get("nota_liberacion", "")
            solicitud.liberar(usuario_libera=request.user, nota=nota)
            messages.success(request, f"Liberaste a {solicitud.persona}. Ahora la federación revisa el pase.")
        else:
            motivo = request.POST.get("motivo_rechazo", "")
            solicitud.rechazar_liberacion(usuario_rechaza=request.user, motivo=motivo)
            messages.info(request, f"Rechazaste la salida de {solicitud.persona}.")
        return redirect("solicitudes_a_liberar")

    return render(request, "federacion_app/liberar_solicitud.html", {"solicitud": solicitud})


# ---------------------------------------------------------------------
# PANTALLA 2: panel de la federación para revisar/aprobar
# ---------------------------------------------------------------------

@login_required
@user_passes_test(es_federacion)
def panel_solicitudes(request):
    pendientes = SolicitudPase.objects.filter(
        estado__in=["pendiente", "en_revision"]
    ).select_related("persona", "club_origen", "club_destino").order_by("fecha_creacion")
    return render(request, "federacion_app/panel_solicitudes.html", {"solicitudes": pendientes})


@login_required
@user_passes_test(es_federacion)
def historial_solicitudes(request):
    """Historial de todas las solicitudes ya resueltas, de cualquier club."""
    solicitudes = SolicitudPase.objects.filter(
        estado__in=["aprobado", "rechazado"]
    ).select_related("persona", "club_origen", "club_destino").order_by("-fecha_resolucion")
    return render(request, "federacion_app/historial_solicitudes.html", {"solicitudes": solicitudes})


@login_required
@user_passes_test(es_federacion)
def revisar_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPase, id=solicitud_id)

    if request.method == "POST":
        form = ResolucionSolicitudForm(request.POST)
        if form.is_valid():
            accion = form.cleaned_data["accion"]
            if accion == "aprobar":
                solicitud.fecha_resolucion = date.today()
                solicitud.aprobar(usuario_resuelve=request.user)
                messages.success(request, f"Solicitud de {solicitud.persona} aprobada.")
            else:
                solicitud.estado = "rechazado"
                solicitud.motivo_rechazo = form.cleaned_data.get("motivo_rechazo", "")
                solicitud.resuelto_por = request.user
                solicitud.fecha_resolucion = date.today()
                solicitud.save()
                messages.info(request, f"Solicitud de {solicitud.persona} rechazada.")
            return redirect("panel_solicitudes")
    else:
        form = ResolucionSolicitudForm()

    return render(request, "federacion_app/revisar_solicitud.html", {
        "solicitud": solicitud, "form": form,
    })


# ---------------------------------------------------------------------
# PANTALLA 3: ficha del jugador con su historial
# ---------------------------------------------------------------------

def _filtrar_padron(request):
    """Lógica de filtro compartida entre la pantalla y las exportaciones."""
    club_id = request.GET.get("club")
    categoria_id = request.GET.get("categoria")
    club_seleccionado = None
    categoria_seleccionada = None
    jugadores = Persona.objects.none()

    if club_id:
        club_seleccionado = get_object_or_404(Club, id=club_id)
        vinculos_activos = Q(vinculos__club=club_seleccionado, vinculos__fecha_fin__isnull=True)

        if categoria_id:
            categoria_seleccionada = get_object_or_404(Categoria, id=categoria_id)
            vinculos_activos &= Q(vinculos__categoria=categoria_seleccionada)

        jugadores = Persona.objects.filter(vinculos_activos).distinct().order_by("apellido")

    return club_seleccionado, categoria_seleccionada, jugadores


@login_required
@user_passes_test(es_federacion)
def importar_excel(request):
    import pandas as pd
    from .forms import ImportarExcelForm

    resultado = None

    if request.method == "POST":
        form = ImportarExcelForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data["archivo"]
            solo_simular = form.cleaned_data["solo_simular"]

            creados, actualizados = 0, 0
            errores, duplicados = [], []
            vinculos_por_persona = {}
            columnas_esperadas = {"documento", "nombre", "apellido", "fecha_nacimiento"}

            def parsear_fecha(valor):
                if pd.isna(valor):
                    return None
                if hasattr(valor, "date"):
                    return valor.date()
                texto = str(valor).strip()
                for formato in (
                    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
                    "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
                ):
                    try:
                        return datetime.strptime(texto, formato).date()
                    except ValueError:
                        continue
                # Último intento: dejar que pandas adivine el formato.
                try:
                    resultado = pd.to_datetime(texto, dayfirst=True, errors="raise")
                    return resultado.date()
                except (ValueError, TypeError):
                    return None

            # Variantes comunes de nombres de columna que se aceptan como equivalentes.
            alias_columnas = {
                "numero de carnet": "numero_carnet", "número de carnet": "numero_carnet",
                "n° de carnet": "numero_carnet", "nro carnet": "numero_carnet",
                "fecha nacimiento": "fecha_nacimiento", "fecha de nacimiento": "fecha_nacimiento",
                "fecha ingreso": "fecha_ingreso", "fecha de ingreso": "fecha_ingreso",
                "categoría": "categoria",
                "requiere carnet": "requiere_carnet",
            }

            def normalizar_columnas(columnas):
                normalizadas = []
                for c in columnas:
                    c = str(c).strip().lower()
                    c = alias_columnas.get(c, c)
                    normalizadas.append(c)
                return normalizadas

            def leer_hoja_con_encabezado_flexible(archivo, nombre_hoja):
                """
                Busca la fila real de encabezados dentro de las primeras 5 filas,
                por si hay filas vacías o de título arriba de los datos.
                """
                crudo = pd.read_excel(archivo, sheet_name=nombre_hoja, header=None, dtype=str)
                for fila_idx in range(min(5, len(crudo))):
                    candidatas = normalizar_columnas(crudo.iloc[fila_idx].fillna(""))
                    if columnas_esperadas.issubset(set(candidatas)):
                        df = pd.read_excel(archivo, sheet_name=nombre_hoja, header=fila_idx, dtype=str)
                        df.columns = normalizar_columnas(df.columns)
                        return df
                # No se encontró una fila de encabezados válida: devuelve la lectura
                # normal (fila 0) para que el mensaje de error liste qué faltó.
                df = pd.read_excel(archivo, sheet_name=nombre_hoja, dtype=str)
                df.columns = normalizar_columnas(df.columns)
                return df

            try:
                excel = pd.ExcelFile(archivo)
            except Exception as e:
                errores.append(f"No se pudo leer el archivo: {e}")
                excel = None

            if excel:
                for nombre_hoja in excel.sheet_names:
                    nombre_club = nombre_hoja.strip()
                    df = leer_hoja_con_encabezado_flexible(archivo, nombre_hoja)

                    faltantes = columnas_esperadas - set(df.columns)
                    if faltantes:
                        errores.append(f"Hoja '{nombre_hoja}': faltan columnas {faltantes}, se omite.")
                        continue

                    club_de_la_hoja, _ = Club.objects.get_or_create(
                        nombre__iexact=nombre_club,
                        defaults={
                            "nombre": nombre_club,
                            "codigo_afiliacion": f"AUTO-{nombre_club[:10].upper()}",
                            "fecha_afiliacion": date.today(),
                        },
                    )

                    for i, fila in df.iterrows():
                        ubicacion = f"Hoja '{nombre_hoja}', fila {i + 2}"
                        try:
                            documento = str(fila["documento"]).strip()
                            if not documento or documento.lower() == "nan":
                                errores.append(f"{ubicacion}: sin documento, se omite")
                                continue

                            # Si la fila trae su propia columna 'club', se usa esa
                            # en vez del nombre de la hoja (útil cuando el archivo
                            # tiene una sola hoja con varios clubes mezclados).
                            if "club" in df.columns and pd.notna(fila.get("club")) and str(fila["club"]).strip():
                                nombre_club_fila = str(fila["club"]).strip()
                                club, _ = Club.objects.get_or_create(
                                    nombre__iexact=nombre_club_fila,
                                    defaults={
                                        "nombre": nombre_club_fila,
                                        "codigo_afiliacion": f"AUTO-{nombre_club_fila[:10].upper()}",
                                        "fecha_afiliacion": date.today(),
                                    },
                                )
                            else:
                                club = club_de_la_hoja

                            fecha_nac = parsear_fecha(fila["fecha_nacimiento"])
                            if not fecha_nac:
                                errores.append(f"{ubicacion}: fecha de nacimiento inválida")
                                continue

                            categoria = None
                            if "categoria" in df.columns and pd.notna(fila.get("categoria")):
                                categoria, _ = Categoria.objects.get_or_create(
                                    nombre__iexact=str(fila["categoria"]).strip(),
                                    defaults={"nombre": str(fila["categoria"]).strip()},
                                )

                            fecha_inicio = date.today()
                            if "fecha_ingreso" in df.columns:
                                f = parsear_fecha(fila.get("fecha_ingreso"))
                                if f:
                                    fecha_inicio = f

                            numero_carnet = ""
                            if "numero_carnet" in df.columns and pd.notna(fila.get("numero_carnet")):
                                numero_carnet = str(fila["numero_carnet"]).strip()

                            requiere_carnet = False
                            if "requiere_carnet" in df.columns and pd.notna(fila.get("requiere_carnet")):
                                requiere_carnet = str(fila["requiere_carnet"]).strip().lower() in ("si", "sí", "1", "true", "x")

                            if not solo_simular:
                                persona, fue_creada = Persona.objects.get_or_create(
                                    documento=documento,
                                    defaults={
                                        "tipo": "jugador",
                                        "nombre": str(fila["nombre"]).strip(),
                                        "apellido": str(fila["apellido"]).strip(),
                                        "fecha_nacimiento": fecha_nac,
                                        "numero_carnet": numero_carnet,
                                        "requiere_carnet": requiere_carnet,
                                    },
                                )
                                if fue_creada:
                                    creados += 1
                                else:
                                    actualizados += 1
                                    duplicados.append(f"{ubicacion}: {documento} aparece en más de una hoja")
                                vinculos_por_persona.setdefault(documento, []).append(
                                    (persona, club, categoria, fecha_inicio)
                                )
                            else:
                                # En modo simulación solo contamos, sin tocar la base.
                                if Persona.objects.filter(documento=documento).exists():
                                    actualizados += 1
                                    duplicados.append(f"{ubicacion}: {documento} aparece en más de una hoja")
                                else:
                                    creados += 1

                        except Exception as e:
                            errores.append(f"{ubicacion}: error inesperado — {e}")

                if not solo_simular:
                    for documento, lista in vinculos_por_persona.items():
                        lista.sort(key=lambda v: v[3])
                        for idx, (persona, club, categoria, fecha_inicio) in enumerate(lista):
                            es_el_ultimo = idx == len(lista) - 1
                            fecha_fin = None if es_el_ultimo else lista[idx + 1][3]

                            if not persona.vinculos.filter(club=club, fecha_inicio=fecha_inicio).exists():
                                if fecha_fin is None:
                                    # Va a quedar como vínculo activo: hay que cerrar
                                    # cualquier otro vínculo activo que ya tuviera
                                    # (de una carga anterior), para no violar la regla
                                    # de "un solo club activo por persona".
                                    persona.vinculos.filter(fecha_fin__isnull=True).exclude(
                                        club=club, fecha_inicio=fecha_inicio
                                    ).update(fecha_fin=fecha_inicio)

                                Vinculo.objects.create(
                                    persona=persona, club=club, categoria=categoria,
                                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                                )

            resultado = {
                "simulado": solo_simular,
                "creados": creados, "actualizados": actualizados,
                "errores": errores, "duplicados": duplicados,
            }
            if not solo_simular:
                messages.success(request, f"Importación completa: {creados} jugadores nuevos.")
    else:
        form = ImportarExcelForm()

    return render(request, "federacion_app/importar_excel.html", {"form": form, "resultado": resultado})


@login_required
@user_passes_test(es_delegado)
def inscribir_torneo(request):
    from .models import InscripcionTorneo, Torneo

    torneos = Torneo.objects.filter(activo=True)
    categorias = Categoria.objects.all().order_by("nombre")
    categoria_id = request.GET.get("categoria") or request.POST.get("categoria_filtro")

    jugadores_qs = Persona.objects.filter(
        vinculos__club=request.user.club, vinculos__fecha_fin__isnull=True
    ).distinct().order_by("apellido")
    if categoria_id:
        jugadores_qs = jugadores_qs.filter(vinculos__categoria_id=categoria_id, vinculos__fecha_fin__isnull=True)

    # Para marcar en la tabla a quiénes ya se inscribió a cada torneo, sin
    # tener que abrir cada uno: se arma un set de (persona_id, torneo_id).
    ya_inscritos = set(
        InscripcionTorneo.objects.filter(club=request.user.club)
        .values_list("persona_id", "torneo_id")
    )

    if request.method == "POST":
        torneo_id = request.POST.get("torneo")
        ids_seleccionados = request.POST.getlist("jugadores")
        torneo = get_object_or_404(Torneo, id=torneo_id) if torneo_id else None

        if not torneo:
            messages.error(request, "Elegí un torneo antes de inscribir.")
        elif not ids_seleccionados:
            messages.error(request, "Marcá al menos un jugador para inscribir.")
        else:
            creadas = 0
            for persona_id in ids_seleccionados:
                if (int(persona_id), torneo.id) in ya_inscritos:
                    continue  # ya estaba inscrito a ese torneo, se salta
                InscripcionTorneo.objects.create(
                    persona_id=persona_id, club=request.user.club,
                    torneo=torneo, inscrito_por=request.user,
                )
                creadas += 1
            messages.success(request, f"Inscribiste {creadas} jugador(es) a {torneo}. La federación va a liquidar el costo.")
            return redirect("inscribir_torneo")

    mis_inscripciones = InscripcionTorneo.objects.filter(club=request.user.club).select_related("persona", "torneo")
    return render(request, "federacion_app/inscribir_torneo.html", {
        "torneos": torneos, "categorias": categorias, "categoria_id": categoria_id,
        "jugadores": jugadores_qs, "ya_inscritos": ya_inscritos,
        "inscripciones": mis_inscripciones,
    })


@login_required
@user_passes_test(es_federacion)
def marcar_pagado(request, inscripcion_id):
    from .models import InscripcionTorneo
    inscripcion = get_object_or_404(InscripcionTorneo, id=inscripcion_id)
    if request.method == "POST":
        inscripcion.pagado = not inscripcion.pagado
        inscripcion.fecha_pago = date.today() if inscripcion.pagado else None
        inscripcion.save()
    return redirect("cobro_masivo")


@login_required
@user_passes_test(es_federacion)
def historial_inscripciones(request):
    from .models import InscripcionTorneo
    inscripciones = InscripcionTorneo.objects.filter(pagado=True).select_related(
        "persona", "club", "torneo"
    ).order_by("-fecha_pago")
    return render(request, "federacion_app/historial_inscripciones.html", {"inscripciones": inscripciones})


@login_required
@user_passes_test(es_federacion)
def cobro_masivo(request):
    """
    Pantalla única de cobro: arriba los totales pendientes por club y
    categoría (de todos los torneos); al elegir un torneo (y opcionalmente
    una categoría), aparece la grilla para tildar los tres conceptos y
    validar el pago. Al validar el pago, el jugador desaparece de la lista.
    """
    from collections import defaultdict
    from .models import InscripcionTorneo, Torneo

    torneos = Torneo.objects.filter(activo=True)
    categorias = Categoria.objects.all().order_by("nombre")
    clubes = Club.objects.all().order_by("nombre")

    # --- Totales pendientes (de todos los torneos, no solo el filtrado) ---
    pendientes_generales = InscripcionTorneo.objects.filter(
        estado="cobrado", pagado=False
    ).select_related("persona", "club")

    totales_club = defaultdict(float)
    totales_categoria = defaultdict(float)
    for i in pendientes_generales:
        monto = float(i.monto_total)
        totales_club[i.club.nombre] += monto
        vinculo = i.persona.vinculos.filter(club=i.club, fecha_fin__isnull=True).first()
        nombre_categoria = vinculo.categoria.nombre if vinculo and vinculo.categoria else "Sin categoría"
        totales_categoria[nombre_categoria] += monto

    total_pagado = sum(
        float(i.monto_total) for i in InscripcionTorneo.objects.filter(pagado=True)
    )

    # --- Grilla filtrada por torneo / categoría / club ---
    torneo_id = request.POST.get("torneo") or request.GET.get("torneo")
    categoria_id = request.POST.get("categoria") or request.GET.get("categoria")
    club_id = request.POST.get("club") or request.GET.get("club")
    torneo = get_object_or_404(Torneo, id=torneo_id) if torneo_id else None

    filas = []
    if torneo:
        qs = InscripcionTorneo.objects.filter(torneo=torneo, pagado=False).select_related("persona", "club")
        if club_id:
            qs = qs.filter(club_id=club_id)
        for i in qs:
            vinculo = i.persona.vinculos.filter(club=i.club, fecha_fin__isnull=True).first()
            cat = vinculo.categoria if vinculo else None
            if categoria_id and (not cat or str(cat.id) != categoria_id):
                continue
            filas.append({
                "inscripcion": i,
                "der_marcado": i.derechos_federativos is not None,
                "fondo_marcado": i.fondo_seleccion is not None,
                "carnet_marcado": i.carnet is not None,
            })

    if request.method == "POST" and torneo:
        cambios, pagos = 0, 0
        for fila in filas:
            i = fila["inscripcion"]
            tocado = False
            if request.POST.get(f"der_{i.id}"):
                i.derechos_federativos = torneo.precio_derechos_federativos
                tocado = True
            if request.POST.get(f"fondo_{i.id}"):
                i.fondo_seleccion = torneo.precio_fondo_seleccion
                tocado = True
            if request.POST.get(f"carnet_{i.id}"):
                i.carnet = torneo.precio_carnet
                tocado = True
            if tocado:
                i.estado = "cobrado"
                i.cobrado_por = request.user
                i.fecha_cobro = date.today()
                cambios += 1

            # Validar el pago: si se tilda, el jugador desaparece de la
            # lista (queda excluido por el filtro pagado=False de arriba).
            if request.POST.get(f"validar_{i.id}"):
                i.pagado = True
                i.fecha_pago = date.today()
                pagos += 1

            if tocado or request.POST.get(f"validar_{i.id}"):
                i.save()

        if cambios or pagos:
            partes = []
            if cambios:
                partes.append(f"{cambios} cobro(s) registrado(s)")
            if pagos:
                partes.append(f"{pagos} pago(s) validado(s)")
            messages.success(request, " y ".join(partes) + ".")

        url = f"/torneos/cobro-masivo/?torneo={torneo.id}"
        if categoria_id:
            url += f"&categoria={categoria_id}"
        if club_id:
            url += f"&club={club_id}"
        return redirect(url)

    return render(request, "federacion_app/cobro_masivo.html", {
        "torneos": torneos, "categorias": categorias, "clubes": clubes,
        "torneo": torneo, "categoria_id": categoria_id, "club_id": club_id, "filas": filas,
        "totales_club": sorted(totales_club.items()),
        "totales_categoria": sorted(totales_categoria.items()),
        "total_general": sum(totales_club.values()),
        "total_pagado": total_pagado,
    })


@login_required
@user_passes_test(es_federacion)
def cobrar_inscripcion(request, inscripcion_id):
    from .models import InscripcionTorneo
    from .forms import CobroInscripcionForm

    inscripcion = get_object_or_404(InscripcionTorneo, id=inscripcion_id)

    if request.method == "POST":
        form = CobroInscripcionForm(request.POST)
        if form.is_valid():
            inscripcion.derechos_federativos = form.cleaned_data["derechos_federativos"]
            inscripcion.fondo_seleccion = form.cleaned_data["fondo_seleccion"]
            inscripcion.carnet = form.cleaned_data["carnet"]
            inscripcion.estado = "cobrado"
            inscripcion.cobrado_por = request.user
            inscripcion.fecha_cobro = date.today()
            inscripcion.save()
            messages.success(request, f"Cobro registrado para {inscripcion.persona}.")
            return redirect("cobro_masivo")
    else:
        form = CobroInscripcionForm(initial={
            "derechos_federativos": inscripcion.derechos_federativos,
            "fondo_seleccion": inscripcion.fondo_seleccion,
            "carnet": inscripcion.carnet,
        })

    return render(request, "federacion_app/cobrar_inscripcion.html", {
        "inscripcion": inscripcion, "form": form,
    })


@login_required
@user_passes_test(es_delegado)
def planilla_partido(request):
    """
    Genera la planilla de buena fe (PDF) para un partido: el delegado
    tilda los jugadores de su plantel y les asigna número de camiseta,
    completa los datos del partido, y descarga el PDF listo para imprimir.
    """
    club = request.user.club
    jugadores_club = Persona.objects.filter(
        vinculos__club=club, vinculos__fecha_fin__isnull=True
    ).distinct().order_by("apellido")

    if request.method == "POST":
        return _generar_pdf_planilla(request, club)

    return render(request, "federacion_app/planilla_partido.html", {
        "jugadores": jugadores_club, "club": club,
    })


def _generar_pdf_planilla(request, club):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from django.contrib.staticfiles import finders
    from django.http import HttpResponse
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("titulo", parent=estilos["Title"], alignment=TA_CENTER, fontSize=20)
    elementos = []

    # --- Encabezado: logo federación | nombre del club | escudo del club ---
    logo_federacion = finders.find("federacion_app/logo.jpg")
    img_federacion = Image(logo_federacion, width=2.5 * cm, height=2.5 * cm) if logo_federacion else ""
    img_club = Image(club.escudo.path, width=2.5 * cm, height=2.5 * cm) if club.escudo else ""

    encabezado = Table(
        [[img_federacion, Paragraph(club.nombre.upper(), estilo_titulo), img_club]],
        colWidths=[3.5 * cm, 11 * cm, 3.5 * cm],
    )
    encabezado.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elementos.append(encabezado)
    elementos.append(Spacer(1, 16))

    # --- Datos del partido ---
    datos = [
        [f"Torneo: {request.POST.get('torneo', '')}", f"Categoria: {request.POST.get('categoria', '')}"],
        [f"Lugar: {request.POST.get('lugar', '')}", f"Fecha: {request.POST.get('fecha', '')}"],
        [f"Delegada/o: {request.POST.get('delegado', '')}", ""],
    ]
    tabla_datos = Table(datos, colWidths=[10 * cm, 8 * cm])
    tabla_datos.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.7, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("SPAN", (0, 2), (1, 2)),
    ]))
    elementos.append(tabla_datos)
    elementos.append(Spacer(1, 14))

    # --- Plantel: hasta 15 jugadores tildados por el delegado + DT/AT/PF ---
    filas = [["", "APELLIDO Y NOMBRE", "CARNET/DNI", "N° CAMISETA"]]
    ids_seleccionados = request.POST.getlist("jugadores")
    seleccionados = list(Persona.objects.filter(id__in=ids_seleccionados))
    # Mantiene el orden en que vinieron tildados en el formulario
    orden = {int(pid): i for i, pid in enumerate(ids_seleccionados)}
    seleccionados.sort(key=lambda p: orden.get(p.id, 999))

    for i in range(1, 16):
        if i <= len(seleccionados):
            p = seleccionados[i - 1]
            nombre_completo = f"{p.apellido}, {p.nombre}"
            carnet = p.numero_carnet or p.documento
            camiseta = request.POST.get(f"camiseta_{p.id}", "")
        else:
            nombre_completo, carnet, camiseta = "", "", ""
        filas.append([str(i), nombre_completo, carnet, camiseta])

    filas.append(["DT", request.POST.get("dt", ""), "", ""])
    filas.append(["AT", request.POST.get("at", ""), "", ""])
    filas.append(["PF", request.POST.get("pf", ""), "", ""])

    tabla_plantel = Table(filas, colWidths=[1.3 * cm, 9 * cm, 4 * cm, 3.7 * cm], repeatRows=1)
    tabla_plantel.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.7, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_plantel)
    elementos.append(Spacer(1, 14))

    # --- Hora de entrega ---
    tabla_hora = Table([[f"HORA DE ENTREGA: {request.POST.get('hora_entrega', '')}"]], colWidths=[18 * cm])
    tabla_hora.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.7, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 5)]))
    elementos.append(tabla_hora)
    elementos.append(Spacer(1, 14))

    # --- Arbitraje / Mesa ---
    pagos = [
        ["", "EFECTIVO", "TRANSFERENCIA", "", "EFECTIVO", "TRANSFERENCIA"],
        ["ARBITRAJE", request.POST.get("arbitraje_efectivo", ""), request.POST.get("arbitraje_transferencia", ""),
         "MESA", request.POST.get("mesa_efectivo", ""), request.POST.get("mesa_transferencia", "")],
    ]
    tabla_pagos = Table(pagos, colWidths=[3 * cm, 3.5 * cm, 3.5 * cm, 2.5 * cm, 2.7 * cm, 2.8 * cm])
    tabla_pagos.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.7, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_pagos)

    doc.build(elementos)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="planilla_{club.nombre}.pdf"'
    return response


@login_required
@user_passes_test(es_federacion)
def padron_club(request):
    """Lista los jugadores activos de un club elegido, con filtro opcional por categoría. Solo federación."""
    clubes = Club.objects.all().order_by("nombre")
    categorias = Categoria.objects.all().order_by("nombre")
    club_seleccionado, categoria_seleccionada, jugadores = _filtrar_padron(request)

    return render(request, "federacion_app/padron_club.html", {
        "clubes": clubes, "categorias": categorias,
        "club_seleccionado": club_seleccionado, "categoria_seleccionada": categoria_seleccionada,
        "jugadores": jugadores,
    })


@login_required
@user_passes_test(es_federacion)
def padron_excel(request):
    import openpyxl
    from openpyxl.styles import Font
    from django.http import HttpResponse

    club_seleccionado, categoria_seleccionada, jugadores = _filtrar_padron(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Padrón"

    titulo = f"Padrón — {club_seleccionado.nombre if club_seleccionado else 'todos los clubes'}"
    if categoria_seleccionada:
        titulo += f" — {categoria_seleccionada.nombre}"
    ws.append([titulo])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])

    ws.append(["Apellido", "Nombre", "Documento", "Categoría", "Desde"])
    for celda in ws[3]:
        celda.font = Font(bold=True)

    for p in jugadores:
        vinculo = p.vinculos.filter(fecha_fin__isnull=True).first()
        ws.append([
            p.apellido, p.nombre, p.documento,
            vinculo.categoria.nombre if vinculo and vinculo.categoria else "",
            vinculo.fecha_inicio.strftime("%d/%m/%Y") if vinculo else "",
        ])

    for col in ws.columns:
        largo = max(len(str(c.value)) if c.value else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = largo + 4

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    nombre_archivo = f"padron_{club_seleccionado.nombre if club_seleccionado else 'general'}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    wb.save(response)
    return response


@login_required
@user_passes_test(es_federacion)
def padron_pdf(request):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from django.http import HttpResponse
    import io

    club_seleccionado, categoria_seleccionada, jugadores = _filtrar_padron(request)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    estilos = getSampleStyleSheet()
    elementos = []

    titulo = f"Padrón — {club_seleccionado.nombre if club_seleccionado else 'todos los clubes'}"
    if categoria_seleccionada:
        titulo += f" — {categoria_seleccionada.nombre}"
    elementos.append(Paragraph(titulo, estilos["Title"]))
    elementos.append(Spacer(1, 12))

    datos = [["Apellido", "Nombre", "Documento", "Categoría", "Desde"]]
    for p in jugadores:
        vinculo = p.vinculos.filter(fecha_fin__isnull=True).first()
        datos.append([
            p.apellido, p.nombre, p.documento,
            vinculo.categoria.nombre if vinculo and vinculo.categoria else "—",
            vinculo.fecha_inicio.strftime("%d/%m/%Y") if vinculo else "—",
        ])

    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fb")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla)

    doc.build(elementos)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    nombre_archivo = f"padron_{club_seleccionado.nombre if club_seleccionado else 'general'}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    return response


@login_required
def ficha_persona(request, persona_id):
    persona = get_object_or_404(Persona, id=persona_id)
    historial = persona.vinculos.select_related("club", "categoria").order_by("-fecha_inicio")

    edad = None
    if persona.fecha_nacimiento:
        hoy = date.today()
        edad = hoy.year - persona.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (persona.fecha_nacimiento.month, persona.fecha_nacimiento.day)
        )

    return render(request, "federacion_app/ficha_persona.html", {
        "persona": persona, "historial": historial, "edad": edad,
    })


@login_required
def buscar_persona(request):
    """Buscador simple por documento, apellido o número de carnet, para llegar a la ficha."""
    resultados = []
    query = request.GET.get("q", "").strip()
    if query:
        resultados = Persona.objects.filter(
            Q(documento__icontains=query) |
            Q(apellido__icontains=query) |
            Q(numero_carnet__icontains=query)
        )
    return render(request, "federacion_app/buscar_persona.html", {
        "resultados": resultados, "query": query,
    })
