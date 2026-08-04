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

    if getattr(request.user, "rol", None) == "federacion":
        from .models import NotificacionAcuse
        acuses_nuevos = NotificacionAcuse.objects.filter(
            fecha_acuse__isnull=False, visto_por_federacion=False
        ).count()
        return {"acuses_nuevos_count": acuses_nuevos}

    return {}
