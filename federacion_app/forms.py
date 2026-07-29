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
    archivo_documentacion = forms.FileField(label="Documentación (DNI, certificado médico)", required=False)

    class Meta:
        model = SolicitudPase
        fields = ["tipo", "categoria_destino"]
        labels = {
            "tipo": "Tipo de solicitud",
            "categoria_destino": "Categoría destino",
        }

    def clean(self):
        cleaned = super().clean()
        documento = cleaned.get("documento")
        tipo = cleaned.get("tipo")

        # Si el jugador no existe todavía, para un alta nueva son
        # obligatorios nombre, apellido y fecha de nacimiento.
        if documento and not Persona.objects.filter(documento=documento).exists():
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
