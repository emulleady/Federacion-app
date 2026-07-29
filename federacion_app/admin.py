from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Usuario, Club, Categoria, Persona, DocumentoPersona,
    Vinculo, SolicitudPase, DocumentoSolicitud, LogAuditoria,
)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Datos de federación", {"fields": ("rol", "club")}),
    )
    list_display = ("username", "rol", "club", "is_staff")


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_afiliacion", "activo", "fecha_afiliacion")
    search_fields = ("nombre", "codigo_afiliacion")


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
    list_display = ("apellido", "nombre", "documento", "tipo", "club_actual")
    search_fields = ("apellido", "nombre", "documento")
    list_filter = ("tipo",)
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
