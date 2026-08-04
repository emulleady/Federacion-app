def sanciones_pendientes_context(request):
    """
    Le agrega a todos los templates la cantidad de sanciones pendientes
    del club del delegado logueado, para mostrar la alerta en el menú
    sin tener que calcularlo en cada vista por separado.
    """
    if request.user.is_authenticated and getattr(request.user, "rol", None) == "delegado" and request.user.club:
        from .models import SancionTarjeta
        cantidad = SancionTarjeta.objects.filter(club=request.user.club, estado="pendiente").count()
        return {"sanciones_pendientes_count": cantidad}
    return {}
