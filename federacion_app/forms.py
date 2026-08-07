from django import forms
from .models import SolicitudPase, Persona, Categoria, DocumentoSolicitud


class SolicitudPaseForm(forms.ModelForm):
    """
    Formulario que usa el delegado para cargar una solicitud nueva.
    club_destino se completa automáticamente con el club del delegado
    en la vista, así que no aparece como campo editable acá.
    """
    documento = forms.CharField(
        label="Documento del jugador",
        max_length=20,
        help_text="Si el jugador ya existe en el sistema, se completan sus datos solos.",
    )
    nombre = forms.CharField(label="Nombre", max_length=100, required=False)
    apellido = forms.CharField(label="Apellido", max_length=100, required=False)
    fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento", required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    foto = forms.ImageField(label="Foto del jugador", required=False)
    numero_carnet = forms.CharField(label="Número de carnet (si ya lo tiene)", max_length=30, required=False)
    requiere_carnet = forms.BooleanField(label="¿Necesita tramitar el carnet?", required=False)
    archivo_documentacion = forms.FileField(label="Documentación (DNI, certificado médico)", required=False)
    formulario_10_firmado = forms.FileField(
        label="Formulario 10 firmado (habilitación de jugador libre/nuevo, si ya lo tenés)",
        required=False,
        help_text="Opcional al cargar la solicitud — también lo podés subir después desde 'Revisar solicitud'.",
    )

    class Meta:
        model = SolicitudPase
        fields = ["tipo", "tipo_pase", "categoria_destino"]
        labels = {
            "tipo": "Tipo de solicitud",
            "tipo_pase": "Modalidad del pase (definitivo o préstamo)",
            "categoria_destino": "Categoría destino",
        }
        widgets = {
            "tipo_pase": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        self.club_delegado = kwargs.pop("club", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        documento = cleaned.get("documento")
        tipo = cleaned.get("tipo")

        if documento:
            ya_existe = Persona.objects.filter(documento=documento).exists()

            # Alta nueva con un DNI que ya está en el sistema: se bloquea
            # solo si el club actual del jugador NO es hermano del club
            # que está cargando la solicitud (ahí sí sería un duplicado
            # real). Si es un club hermano (misma familia, ej: "Real
            # Madrid" y "Real Madrid Azul"), se permite — un jugador
            # puede tener varios clubes activos dentro de la misma familia.
            if tipo == "alta_nueva" and ya_existe:
                persona_existente = Persona.objects.get(documento=documento)
                club_existente = persona_existente.club_actual
                es_hermano = (
                    club_existente and self.club_delegado and
                    self.club_delegado.es_hermano_de(club_existente)
                )
                if club_existente and not es_hermano:
                    raise forms.ValidationError(
                        f"Ese documento ya está registrado a nombre de {persona_existente} "
                        f"(club actual: {club_existente}). "
                        f"Si necesitás sumarlo a tu club, usá 'Pase entre clubes' en vez de 'Alta de jugador nuevo'."
                    )

            # Si el jugador no existe todavía, para un alta nueva son
            # obligatorios nombre, apellido y fecha de nacimiento.
            if not ya_existe:
                if tipo == "alta_nueva":
                    faltantes = [
                        campo for campo in ("nombre", "apellido", "fecha_nacimiento")
                        if not cleaned.get(campo)
                    ]
                    if faltantes:
                        raise forms.ValidationError(
                            f"El jugador no existe en el sistema todavía. "
                            f"Completá también: {', '.join(faltantes)}."
                        )
                else:
                    raise forms.ValidationError(
                        "Ese documento no está registrado. Para un pase o cambio de "
                        "categoría, el jugador ya tiene que existir en el sistema."
                    )
        return cleaned


class ResolucionSolicitudForm(forms.Form):
    """Formulario simple que usa la federación para aprobar o rechazar."""
    ACCION_CHOICES = [
        ("aprobar", "Aprobar"),
        ("rechazar", "Rechazar"),
    ]
    accion = forms.ChoiceField(choices=ACCION_CHOICES, widget=forms.RadioSelect)
    motivo_rechazo = forms.CharField(
        label="Motivo (solo si rechazás)", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class InscripcionTorneoForm(forms.Form):
    """El delegado elige el torneo y el documento del jugador (de su propio club)."""
    torneo = forms.ModelChoiceField(queryset=None, label="Torneo")
    documento = forms.CharField(label="Documento del jugador", max_length=20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Torneo
        self.fields["torneo"].queryset = Torneo.objects.filter(activo=True)


class CobroInscripcionForm(forms.Form):
    """La federación completa los cinco conceptos al procesar la inscripción."""
    derechos_federativos = forms.DecimalField(label="Derechos federativos ($)", max_digits=10, decimal_places=2, required=False)
    fondo_seleccion = forms.DecimalField(label="Fondo de selección ($)", max_digits=10, decimal_places=2, required=False)
    carnet = forms.DecimalField(label="Carnet ($)", max_digits=10, decimal_places=2, required=False)
    jugador_libre = forms.DecimalField(label="Jugador libre ($)", max_digits=10, decimal_places=2, required=False)
    fichaje_nuevo = forms.DecimalField(label="Fichaje nuevo ($)", max_digits=10, decimal_places=2, required=False)


class ImportarExcelForm(forms.Form):
    """Formulario para que la federación suba el Excel histórico desde la web."""
    archivo = forms.FileField(
        label="Archivo Excel (.xlsx)",
        help_text="Una hoja por club. Columnas esperadas: documento, nombre, apellido, "
                  "fecha_nacimiento, categoria (opcional), fecha_ingreso (opcional), "
                  "numero_carnet (opcional), requiere_carnet (opcional: si/no).",
    )
    solo_simular = forms.BooleanField(
        label="Solo simular (no guarda nada, solo muestra el resultado)",
        required=False, initial=True,
    )


class TecnicoQuickForm(forms.Form):
    """Alta rápida de un miembro del cuerpo técnico, desde la pantalla del Formulario 12."""
    documento = forms.CharField(label="Documento", max_length=20)
    nombre = forms.CharField(label="Nombre", max_length=100)
    apellido = forms.CharField(label="Apellido", max_length=100)
    rol_tecnico = forms.ChoiceField(label="Rol", choices=Persona.ROL_TECNICO_CHOICES)
