from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import date

from .models import Persona, SolicitudPase, Vinculo, DocumentoSolicitud
from .forms import SolicitudPaseForm, ResolucionSolicitudForm


def es_delegado(usuario):
    return usuario.is_authenticated and usuario.rol == "delegado"


def es_federacion(usuario):
    return usuario.is_authenticated and usuario.rol == "federacion"


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

            messages.success(request, "Solicitud enviada. La federación la va a revisar.")
            return redirect("mis_solicitudes")
    else:
        form = SolicitudPaseForm()

    return render(request, "federacion_app/nueva_solicitud.html", {"form": form})


@login_required
@user_passes_test(es_delegado)
def mis_solicitudes(request):
    """Lista de solicitudes que cargó el delegado, con su estado."""
    solicitudes = SolicitudPase.objects.filter(
        club_destino=request.user.club
    ).select_related("persona", "club_origen", "club_destino")
    return render(request, "federacion_app/mis_solicitudes.html", {"solicitudes": solicitudes})


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

@login_required
def ficha_persona(request, persona_id):
    persona = get_object_or_404(Persona, id=persona_id)
    historial = persona.vinculos.select_related("club", "categoria").order_by("-fecha_inicio")
    return render(request, "federacion_app/ficha_persona.html", {
        "persona": persona, "historial": historial,
    })


@login_required
def buscar_persona(request):
    """Buscador simple por documento o apellido, para llegar a la ficha."""
    resultados = []
    query = request.GET.get("q", "").strip()
    if query:
        resultados = Persona.objects.filter(
            documento__icontains=query
        ) | Persona.objects.filter(apellido__icontains=query)
    return render(request, "federacion_app/buscar_persona.html", {
        "resultados": resultados, "query": query,
    })
