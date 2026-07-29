"""
Modelo de datos - Sistema de gestión de la federación deportiva

Cubre: personas (jugadores y cuerpo técnico), clubes, historial de
vínculos, solicitudes de pase/alta, documentación adjunta y usuarios
con roles (delegado de club / administrador de federación).

Pensado para Django + PostgreSQL. Ajustar nombres de campos al
reglamento real de la federación (categorías, tipos de documento, etc).
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


# ---------------------------------------------------------------------
# USUARIOS Y ROLES
# ---------------------------------------------------------------------

class Usuario(AbstractUser):
    """
    Extiende el usuario de Django. El rol determina qué puede ver/hacer
    en el sistema. Un delegado solo opera sobre su propio club.
    """
    ROL_CHOICES = [
        ("delegado", "Delegado de club"),
        ("federacion", "Administrador de federación"),
    ]
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    club = models.ForeignKey(
        "Club", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="delegados",
        help_text="Solo aplica si rol='delegado'"
    )

    def clean(self):
        if self.rol == "delegado" and not self.club:
            raise ValidationError("Un delegado debe tener un club asignado.")


# ---------------------------------------------------------------------
# CLUBES
# ---------------------------------------------------------------------

class Club(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    codigo_afiliacion = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=255, blank=True)
    fecha_afiliacion = models.DateField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    """Ej: Primera, Reserva, Sub-17, Sub-15, etc."""
    nombre = models.CharField(max_length=50, unique=True)
    edad_minima = models.PositiveSmallIntegerField(null=True, blank=True)
    edad_maxima = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return self.nombre


# ---------------------------------------------------------------------
# PERSONAS (jugadores y cuerpo técnico)
# ---------------------------------------------------------------------

class Persona(models.Model):
    """
    Entidad única para jugadores y miembros de cuerpo técnico.
    Un mismo documento de identidad nunca puede duplicarse: esto es lo
    que permite armar el historial real de cada persona.
    """
    TIPO_CHOICES = [
        ("jugador", "Jugador"),
        ("tecnico", "Cuerpo técnico"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    documento = models.CharField(max_length=20, unique=True)
    fecha_nacimiento = models.DateField()
    nacionalidad = models.CharField(max_length=50, blank=True)
    foto = models.ImageField(upload_to="fotos_personas/", null=True, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["documento"])]
        verbose_name_plural = "Personas"

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.documento})"

    @property
    def club_actual(self):
        vinculo = self.vinculos.filter(fecha_fin__isnull=True).first()
        return vinculo.club if vinculo else None


class DocumentoPersona(models.Model):
    """DNI escaneado, certificado médico, foto carnet, etc."""
    TIPO_CHOICES = [
        ("dni", "DNI"),
        ("certificado_medico", "Certificado médico"),
        ("foto_carnet", "Foto carnet"),
        ("otro", "Otro"),
    ]
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="documentos")
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    archivo = models.FileField(upload_to="documentos_personas/")
    fecha_carga = models.DateTimeField(auto_now_add=True)
    vencimiento = models.DateField(null=True, blank=True)


# ---------------------------------------------------------------------
# VÍNCULO (esto ES el historial: jugador/técnico <-> club en el tiempo)
# ---------------------------------------------------------------------

class Vinculo(models.Model):
    """
    Cada fila = un período de una persona en un club/categoría.
    fecha_fin nula = vínculo activo. Nunca se borra un vínculo viejo:
    se cierra (se le pone fecha_fin) y se crea uno nuevo. Así queda
    el historial completo sin perder nada.
    """
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="vinculos")
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="vinculos")
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, null=True, blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    numero_camiseta = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_inicio"]
        constraints = [
            # Evita que una persona tenga dos vínculos activos a la vez
            models.UniqueConstraint(
                fields=["persona"],
                condition=models.Q(fecha_fin__isnull=True),
                name="unico_vinculo_activo_por_persona",
            )
        ]

    def __str__(self):
        estado = "activo" if not self.fecha_fin else f"hasta {self.fecha_fin}"
        return f"{self.persona} en {self.club} ({estado})"


# ---------------------------------------------------------------------
# SOLICITUDES (altas nuevas y pases entre clubes)
# ---------------------------------------------------------------------

class SolicitudPase(models.Model):
    """
    Cubre dos casos con el mismo flujo:
    - Alta nueva: club_origen queda vacío, persona puede ser nueva.
    - Pase: club_origen y club_destino completos (incluye el caso
      "mismo club, otra categoría/equipo", donde origen == destino).
    """
    TIPO_CHOICES = [
        ("alta_nueva", "Alta de jugador nuevo"),
        ("pase", "Pase entre clubes"),
        ("cambio_categoria", "Cambio de categoría/equipo (mismo club)"),
    ]
    ESTADO_CHOICES = [
        ("pendiente_liberacion", "Esperando liberación del club de origen"),
        ("pendiente", "Pendiente (federación)"),
        ("en_revision", "En revisión"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="solicitudes")
    club_origen = models.ForeignKey(
        Club, null=True, blank=True, on_delete=models.PROTECT,
        related_name="solicitudes_salida"
    )
    club_destino = models.ForeignKey(
        Club, on_delete=models.PROTECT, related_name="solicitudes_entrada"
    )
    categoria_destino = models.ForeignKey(Categoria, on_delete=models.PROTECT, null=True, blank=True)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    creado_por = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name="solicitudes_creadas"
    )
    resuelto_por = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="solicitudes_resueltas"
    )
    motivo_rechazo = models.TextField(blank=True)
    nota_liberacion = models.TextField(
        blank=True,
        help_text="Comentario opcional del club de origen al liberar (ej: valor del pase, condiciones)."
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def liberar(self, usuario_libera, nota=""):
        """
        El delegado del club de origen aprueba que el jugador se vaya.
        Esto NO cierra el vínculo todavía — solo destraba la solicitud
        para que la federación la revise y apruebe de forma definitiva.
        """
        self.estado = "pendiente"
        self.nota_liberacion = nota
        self.save()

    def rechazar_liberacion(self, usuario_rechaza, motivo=""):
        self.estado = "rechazado"
        self.motivo_rechazo = motivo or "Rechazado por el club de origen."
        self.resuelto_por = usuario_rechaza
        self.save()

    def aprobar(self, usuario_resuelve):
        """
        Al aprobar: cierra el vínculo activo anterior (si existe) y
        crea el nuevo vínculo con el club destino.
        """
        vinculo_anterior = self.persona.vinculos.filter(fecha_fin__isnull=True).first()
        if vinculo_anterior:
            vinculo_anterior.fecha_fin = self.fecha_resolucion or models.functions.Now()
            vinculo_anterior.save()

        Vinculo.objects.create(
            persona=self.persona,
            club=self.club_destino,
            categoria=self.categoria_destino,
            fecha_inicio=self.fecha_resolucion or models.functions.Now(),
        )

        self.estado = "aprobado"
        self.resuelto_por = usuario_resuelve
        self.save()


class DocumentoSolicitud(models.Model):
    """Documentación adjunta a una solicitud puntual (ej: nota de liberación del club origen)."""
    solicitud = models.ForeignKey(SolicitudPase, on_delete=models.CASCADE, related_name="documentos")
    archivo = models.FileField(upload_to="documentos_solicitudes/")
    descripcion = models.CharField(max_length=150, blank=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)


# ---------------------------------------------------------------------
# AUDITORÍA (recomendado para un sistema con múltiples clubes operando)
# ---------------------------------------------------------------------

class LogAuditoria(models.Model):
    """
    Registro simple de quién hizo qué y cuándo. Útil para resolver
    disputas entre clubes ("yo lo cargué antes", "quién aprobó esto").
    """
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=100)
    modelo_afectado = models.CharField(max_length=50)
    objeto_id = models.PositiveIntegerField()
    detalle = models.JSONField(default=dict, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
