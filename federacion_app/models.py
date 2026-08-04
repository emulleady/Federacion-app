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
        ("consejo_disciplina", "Consejo de disciplina"),
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
    escudo = models.ImageField(upload_to="escudos_clubes/", null=True, blank=True)

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
    ROL_TECNICO_CHOICES = [
        ("dt", "DT"),
        ("ayudante", "Ayudante técnico"),
        ("pf", "Preparador físico"),
        ("delegado", "Delegado"),
        ("otro", "Otro"),
    ]
    rol_tecnico = models.CharField(
        max_length=10, choices=ROL_TECNICO_CHOICES, blank=True,
        help_text="Solo si tipo='tecnico'",
    )
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    documento = models.CharField(max_length=20, unique=True)
    fecha_nacimiento = models.DateField()
    nacionalidad = models.CharField(max_length=50, blank=True)
    foto = models.ImageField(upload_to="fotos_personas/", null=True, blank=True)
    numero_carnet = models.CharField(max_length=30, blank=True, help_text="Número de carnet de la federación, si ya lo tiene.")
    requiere_carnet = models.BooleanField(default=False, help_text="Marcar si hay que tramitarle el carnet.")
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
        ("autorizacion_fichaje", "Autorización de fichaje firmada (Form. 08)"),
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

# ---------------------------------------------------------------------
# TORNEOS E INSCRIPCIONES (con los cobros de la federación)
# ---------------------------------------------------------------------

class Torneo(models.Model):
    nombre = models.CharField(max_length=150)
    temporada = models.CharField(max_length=20, help_text="Ej: 2026, Apertura 2026")
    activo = models.BooleanField(default=True)

    # Precios fijos por concepto para este torneo. Se cargan una sola vez
    # y se usan para el cobro masivo (tildar en vez de tipear cada monto).
    precio_derechos_federativos = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_fondo_seleccion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_carnet = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-temporada", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.temporada})"


class PresentacionFormulario12(models.Model):
    """
    Una presentación del Formulario 12 por club/torneo/categoría. El
    delegado la genera y sube el papel firmado; la federación la revisa
    y recién con su aprobación los jugadores quedan activos en el torneo.
    """
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente de firma/aprobación"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado"),
    ]

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="presentaciones_formulario12")
    torneo = models.ForeignKey(Torneo, on_delete=models.PROTECT, related_name="presentaciones_formulario12")
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, null=True, blank=True)

    jugadores = models.ManyToManyField(Persona, related_name="presentaciones_como_jugador", blank=True)
    tecnicos = models.ManyToManyField(Persona, related_name="presentaciones_como_tecnico", blank=True)

    archivo_firmado = models.FileField(upload_to="formularios12_firmados/", null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    motivo_rechazo = models.TextField(blank=True)

    creado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="presentaciones_creadas")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    aprobado_por = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL, related_name="presentaciones_aprobadas"
    )
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Form. 12 — {self.club} — {self.torneo} — {self.categoria}"


class InscripcionTorneo(models.Model):
    """
    Inscripción de un jugador a un torneo puntual. Aunque el jugador ya
    pertenezca al club, la federación cobra estos tres conceptos por
    separado, con montos que varían torneo a torneo.
    """
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente de cobro"),
        ("cobrado", "Cobrado"),
    ]

    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="inscripciones_torneo")
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="inscripciones_torneo")
    torneo = models.ForeignKey(Torneo, on_delete=models.PROTECT, related_name="inscripciones")

    derechos_federativos = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fondo_seleccion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    carnet = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    pagado = models.BooleanField(default=False, help_text="Marcar cuando el club efectivamente pagó.")
    fecha_pago = models.DateTimeField(null=True, blank=True)
    inscrito_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="inscripciones_creadas")
    cobrado_por = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL, related_name="inscripciones_cobradas"
    )
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    fecha_cobro = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_inscripcion"]

    @property
    def monto_total(self):
        return sum(v for v in [self.derechos_federativos, self.fondo_seleccion, self.carnet] if v is not None)

    def __str__(self):
        return f"{self.persona} — {self.torneo}"


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


# ---------------------------------------------------------------------
# TARJETAS Y SANCIONES
# ---------------------------------------------------------------------

class Tarjeta(models.Model):
    """Una tarjeta individual cargada por la federación después de un partido."""
    TIPO_CHOICES = [
        ("amarilla", "Amarilla"),
        ("azul_indirecta", "Azul indirecta"),
        ("azul_directa", "Azul directa"),
    ]

    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="tarjetas")
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="tarjetas")
    torneo = models.ForeignKey(Torneo, on_delete=models.PROTECT, null=True, blank=True, related_name="tarjetas")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    fecha_partido = models.DateField()
    observacion = models.CharField(max_length=200, blank=True)

    cargada_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="tarjetas_cargadas")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_partido"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.persona} ({self.fecha_partido})"


class SancionTarjeta(models.Model):
    """
    Se genera automáticamente al llegar a un umbral (4ta amarilla, 2da
    azul indirecta, o cualquier azul directa). El club paga (sube el
    comprobante) o cumple la fecha; la federación resuelve.
    """
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("pagado", "Pagado"),
        ("cumplido", "Fecha cumplida"),
    ]

    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="sanciones")
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="sanciones")
    tipo_tarjeta = models.CharField(max_length=20, choices=Tarjeta.TIPO_CHOICES)
    numero_ocurrencia = models.PositiveSmallIntegerField(help_text="1ra, 2da, 3ra... vez que se llega a este umbral")
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    comprobante_pago = models.FileField(upload_to="comprobantes_sanciones/", null=True, blank=True)

    fecha_generada = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    resuelto_por = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL, related_name="sanciones_resueltas"
    )

    class Meta:
        ordering = ["-fecha_generada"]
        constraints = [
            models.UniqueConstraint(
                fields=["persona", "tipo_tarjeta", "numero_ocurrencia"],
                name="unica_sancion_por_umbral",
            )
        ]

    def __str__(self):
        return f"{self.persona} — {self.get_tipo_tarjeta_display()} #{self.numero_ocurrencia}"


class SancionDisciplinaria(models.Model):
    """
    Sanción importante cargada por el Consejo de Disciplina — distinta
    de las sanciones automáticas por acumulación de tarjetas. Va con un
    informe adjunto que respalda la decisión.
    """
    ESTADO_CHOICES = [
        ("activa", "Activa"),
        ("cumplida", "Cumplida"),
    ]

    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="sanciones_disciplinarias")
    club = models.ForeignKey(Club, on_delete=models.PROTECT, null=True, blank=True, related_name="sanciones_disciplinarias")
    motivo = models.TextField()
    informe = models.FileField(upload_to="informes_disciplina/", null=True, blank=True)
    fecha_sancion = models.DateField()
    cantidad_fechas = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Cantidad de fechas de suspensión, si corresponde")
    cantidad_anios = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Cantidad de años de suspensión, si corresponde en vez de fechas")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="activa")

    cargada_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="sanciones_disciplinarias_cargadas")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_sancion"]

    def __str__(self):
        return f"{self.persona} — {self.motivo[:40]}"


# ---------------------------------------------------------------------
# NOTIFICACIONES E INSTITUCIONAL
# ---------------------------------------------------------------------

class Notificacion(models.Model):
    """
    Aviso de la federación a los clubes (cambios, avisos, recordatorios).
    Si no se elige ningún club destinatario, se manda a todos.
    """
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    destinatarios = models.ManyToManyField(
        Club, blank=True, related_name="notificaciones",
        help_text="Dejar vacío para enviar a todos los clubes.",
    )
    leida_por = models.ManyToManyField(Usuario, blank=True, related_name="notificaciones_leidas")

    creada_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="notificaciones_creadas")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.titulo

    def es_para(self, club):
        return not self.destinatarios.exists() or self.destinatarios.filter(id=club.id).exists()


class NotificacionAcuse(models.Model):
    """
    Acuse de recibo de un club sobre una notificación, con respuesta
    opcional. Una fila por club por notificación.
    """
    notificacion = models.ForeignKey(Notificacion, on_delete=models.CASCADE, related_name="acuses")
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="acuses_notificaciones")

    acusado_por = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL)
    fecha_acuse = models.DateTimeField(null=True, blank=True)

    respuesta = models.TextField(blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    visto_por_federacion = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notificacion", "club"], name="un_acuse_por_club_por_notificacion")
        ]

    def __str__(self):
        return f"Acuse de {self.club} — {self.notificacion.titulo}"


class DocumentoInstitucional(models.Model):
    """Reglamentos, formularios y otros documentos que la federación pone a disposición de los clubes."""
    TIPO_CHOICES = [
        ("reglamento", "Reglamento"),
        ("formulario", "Formulario"),
        ("circular", "Circular"),
        ("otro", "Otro"),
    ]

    titulo = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="otro")
    archivo = models.FileField(upload_to="institucional/")
    descripcion = models.CharField(max_length=250, blank=True)

    subido_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="documentos_institucionales")
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_subida"]

    def __str__(self):
        return self.titulo
