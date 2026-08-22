def sanciones_pendientes_context(request):
    """
    Le agrega a todos los templates las alertas del menú: sanciones
    pendientes y notificaciones no leídas (delegado), o acuses nuevos
    de los clubes (federación) — sin calcularlo en cada vista.
    """
    if not request.user.is_authenticated:
        return {}

    if getattr(request.user, "rol", None) == "delegado" and request.user.club:
        from .models import SancionTarjeta, Notificacion

        cantidad_sanciones = SancionTarjeta.objects.filter(club=request.user.club, estado="pendiente").count()

        club = request.user.club
        todas = Notificacion.objects.prefetch_related("destinatarios", "leida_por")
        no_leidas = sum(
            1 for n in todas
            if n.es_para(club) and not n.leida_por.filter(id=request.user.id).exists()
        )

        return {"sanciones_pendientes_count": cantidad_sanciones, "notificaciones_no_leidas_count": no_leidas}

    if getattr(request.user, "rol", None) in ("federacion", "consejo_disciplina"):
        from .models import InformeArbitro
        informes_nuevos = InformeArbitro.objects.filter(visto_por_federacion=False).count()
        datos = {"informes_nuevos_count": informes_nuevos}
        if request.user.rol == "federacion":
            from .models import NotificacionAcuse, Persona
            acuses_nuevos = NotificacionAcuse.objects.filter(
                fecha_acuse__isnull=False, visto_por_federacion=False
            ).count()
            pedidos_carnet = Persona.objects.filter(requiere_carnet=True, numero_carnet="").count()
            datos["acuses_nuevos_count"] = acuses_nuevos
            datos["pedidos_carnet_count"] = pedidos_carnet
        return datos

    if getattr(request.user, "rol", None) == "arbitro":
        from .models import RespuestaInforme
        respuestas_nuevas = RespuestaInforme.objects.filter(
            informe__arbitro=request.user, visto_por_arbitro=False
        ).count()
        return {"respuestas_nuevas_arbitro_count": respuestas_nuevas}

    return {}
