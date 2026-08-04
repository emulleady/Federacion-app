from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Usuario, Club, Categoria, Persona, DocumentoPersona,
    Vinculo, SolicitudPase, DocumentoSolicitud, LogAuditoria,
    Torneo, InscripcionTorneo, PresentacionFormulario12,
    Tarjeta, SancionTarjeta, SancionDisciplinaria,
)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Datos de federación", {"fields": ("rol", "club")}),
    )
    list_display = ("username", "rol", "club", "is_staff")


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_afiliacion", "activo", "fecha_afiliacion", "vista_escudo")
    search_fields = ("nombre", "codigo_afiliacion")

    def vista_escudo(self, obj):
        from django.utils.html import format_html
        if obj.escudo:
            return format_html('<img src="{}" style="height:48px; border-radius:4px;">', obj.escudo.url)
        return "—"
    vista_escudo.short_description = "Escudo"


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "edad_minima", "edad_maxima")


class DocumentoPersonaInline(admin.TabularInline):
    model = DocumentoPersona
    extra = 0


class VinculoInline(admin.TabularInline):
    model = Vinculo
    extra = 0
    fk_name = "persona"


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ("apellido", "nombre", "documento", "tipo", "rol_tecnico", "club_actual", "numero_carnet", "requiere_carnet")
    search_fields = ("apellido", "nombre", "documento", "numero_carnet")
    list_filter = ("tipo", "rol_tecnico", "requiere_carnet")
    inlines = [VinculoInline, DocumentoPersonaInline]


@admin.register(Vinculo)
class VinculoAdmin(admin.ModelAdmin):
    list_display = ("persona", "club", "categoria", "fecha_inicio", "fecha_fin")
    list_filter = ("club", "categoria")
    search_fields = ("persona__apellido", "persona__nombre", "persona__documento")


class DocumentoSolicitudInline(admin.TabularInline):
    model = DocumentoSolicitud
    extra = 0


@admin.register(SolicitudPase)
class SolicitudPaseAdmin(admin.ModelAdmin):
    list_display = ("persona", "tipo", "club_origen", "club_destino", "estado", "fecha_creacion")
    list_filter = ("estado", "tipo")
    search_fields = ("persona__apellido", "persona__nombre", "persona__documento")
    inlines = [DocumentoSolicitudInline]


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "modelo_afectado")
    list_filter = ("modelo_afectado",)


@admin.register(Torneo)
class TorneoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "temporada", "activo", "precio_derechos_federativos", "precio_fondo_seleccion", "precio_carnet")
    list_filter = ("activo",)


@admin.register(InscripcionTorneo)
class InscripcionTorneoAdmin(admin.ModelAdmin):
    list_display = ("persona", "club", "torneo", "estado", "monto_total", "pagado")
    list_filter = ("estado", "pagado", "torneo")
    search_fields = ("persona__apellido", "persona__documento")


@admin.register(PresentacionFormulario12)
class PresentacionFormulario12Admin(admin.ModelAdmin):
    list_display = ("club", "torneo", "categoria", "estado", "fecha_creacion", "aprobado_por")
    list_filter = ("estado", "torneo", "categoria")
    search_fields = ("club__nombre",)


@admin.register(Tarjeta)
class TarjetaAdmin(admin.ModelAdmin):
    list_display = ("persona", "club", "tipo", "fecha_partido", "torneo")
    list_filter = ("tipo", "torneo")
    search_fields = ("persona__apellido", "persona__documento")


@admin.register(SancionTarjeta)
class SancionTarjetaAdmin(admin.ModelAdmin):
    list_display = ("persona", "club", "tipo_tarjeta", "numero_ocurrencia", "monto", "estado")
    list_filter = ("estado", "tipo_tarjeta")
    search_fields = ("persona__apellido", "persona__documento")


@admin.register(SancionDisciplinaria)
class SancionDisciplinariaAdmin(admin.ModelAdmin):
    list_display = ("persona", "club", "fecha_sancion", "estado", "cargada_por")
    list_filter = ("estado",)
    search_fields = ("persona__apellido", "persona__documento", "motivo")
